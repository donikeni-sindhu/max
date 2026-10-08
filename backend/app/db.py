"""Service-role Supabase client. DEMO_MODE falls back to an in-memory store."""

from __future__ import annotations

import copy
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.config import get_settings
from app.models import DEMO_MISSION_ID, DEMO_USER_ID, WorldStateData

_memory: dict[str, Any] = {
    "missions": {},
    "concepts": [],
    "resources": [],
    "world": {},
    "events": [],
    "character": {},
    "event_id": 1,
}
_client: Any = None
_use_memory = False
_probed = False
_logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def using_memory() -> bool:
    _probe()
    return _use_memory


def _probe() -> None:
    global _client, _use_memory, _probed
    if _probed:
        return
    _probed = True
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        _use_memory = True
        return
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        client.table("missions").select("id").limit(1).execute()
        _client = client
    except Exception:
        if settings.demo_mode:
            _use_memory = True
        else:
            raise


def client() -> Any:
    _probe()
    if _client is None:
        raise RuntimeError("Supabase service-role client is not available")
    return _client


def create_mission(user_id: UUID, goal: str, target_title: str | None = None) -> dict[str, Any]:
    mission_id = uuid4()
    row = {
        "id": str(mission_id),
        "user_id": str(user_id),
        "goal": goal,
        "target_title": target_title,
        "status": "created",
        "created_at": _now(),
        "updated_at": _now(),
    }
    state = WorldStateData(goal=goal).model_dump(mode="json")
    if using_memory():
        _memory["missions"][row["id"]] = row
        _memory["world"][row["id"]] = {"mission_id": row["id"], "state": state, "updated_at": _now()}
        _ensure_character(str(user_id))
        return row
    try:
        client().table("profiles").upsert({"id": str(user_id), "display_name": "Learner"}).execute()
    except Exception:
        pass
    inserted = client().table("missions").insert(row).execute()
    saved = inserted.data[0]
    client().table("world_state").upsert(
        {"mission_id": saved["id"], "state": state, "updated_at": _now()}
    ).execute()
    _ensure_character(str(user_id))
    return saved


def update_mission(mission_id: UUID, **fields: Any) -> None:
    fields["updated_at"] = _now()
    key = str(mission_id)
    if using_memory():
        _memory["missions"][key].update(fields)
        return
    client().table("missions").update(fields).eq("id", key).execute()


def get_bundle(mission_id: UUID) -> dict[str, Any] | None:
    key = str(mission_id)
    if using_memory():
        mission = _memory["missions"].get(key)
        if mission is None:
            return None
        concepts = [row for row in _memory["concepts"] if row["mission_id"] == key]
        resources = [row for row in _memory["resources"] if row["mission_id"] == key]
        return {
            "mission": copy.deepcopy(mission),
            "concepts": sorted(copy.deepcopy(concepts), key=lambda row: row["order_index"]),
            "resources": copy.deepcopy(resources),
            "world_state": copy.deepcopy(_memory["world"].get(key)),
            "events": [row for row in _memory["events"] if row["mission_id"] == key],
        }
    mission_res = client().table("missions").select("*").eq("id", key).limit(1).execute()
    if not mission_res.data:
        return None
    concepts = (
        client().table("concepts").select("*").eq("mission_id", key).order("order_index").execute().data
    )
    resources = client().table("resources").select("*").eq("mission_id", key).execute().data
    world = client().table("world_state").select("*").eq("mission_id", key).limit(1).execute().data
    events = (
        client()
        .table("agent_events")
        .select("*")
        .eq("mission_id", key)
        .order("created_at")
        .execute()
        .data
    )
    return {
        "mission": mission_res.data[0],
        "concepts": concepts,
        "resources": resources,
        "world_state": world[0] if world else None,
        "events": events,
    }


def replace_concepts(mission_id: UUID, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = str(mission_id)
    rows = []
    for concept in concepts:
        rows.append(
            {
                "id": str(uuid4()),
                "mission_id": key,
                "name": concept["name"],
                "level": concept["level"],
                "explanation": concept["explanation"],
                "order_index": concept["order_index"],
                "status": concept.get("status", "pending"),
            }
        )
    if using_memory():
        _memory["concepts"] = [row for row in _memory["concepts"] if row["mission_id"] != key]
        _memory["concepts"].extend(rows)
        return rows
    client().table("concepts").delete().eq("mission_id", key).execute()
    if rows:
        return client().table("concepts").insert(rows).execute().data
    return []


def replace_resources(mission_id: UUID, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = str(mission_id)
    bundle = get_bundle(mission_id)
    # Normalize whitespace and case because model-generated concept names may differ only in formatting.
    by_name = {re.sub(r"\s+", " ", str(row["name"])).strip().casefold(): row["id"] for row in (bundle or {}).get("concepts", [])}
    rows = []
    for resource in resources:
        normalized_name = re.sub(r"\s+", " ", str(resource.get("concept_name") or "")).strip().casefold()
        concept_id = resource.get("concept_id") or by_name.get(normalized_name)
        if normalized_name and concept_id is None:
            _logger.warning("Could not link resource %r to a concept in mission %s", resource.get("title"), key)
        rows.append(
            {
                "id": str(uuid4()),
                "mission_id": key,
                "concept_id": concept_id,
                "title": resource["title"],
                "url": resource["url"],
                "source": resource.get("source"),
                "score": resource.get("score"),
                "selected": bool(resource.get("selected", False)),
            }
        )
    if using_memory():
        _memory["resources"] = [row for row in _memory["resources"] if row["mission_id"] != key]
        _memory["resources"].extend(rows)
        return rows
    client().table("resources").delete().eq("mission_id", key).execute()
    if rows:
        return client().table("resources").insert(rows).execute().data
    return []


def save_world(mission_id: UUID, state: dict[str, Any]) -> None:
    key = str(mission_id)
    current = WorldStateData.model_validate(state).model_dump(mode="json")
    row = {"mission_id": key, "state": current, "updated_at": _now()}
    if using_memory():
        _memory["world"][key] = row
        return
    client().table("world_state").upsert(row).execute()


def patch_world(mission_id: UUID, **parts: Any) -> dict[str, Any]:
    bundle = get_bundle(mission_id)
    raw = (bundle or {}).get("world_state", {}) or {}
    state = dict(raw.get("state") or {})
    state.update(parts)
    save_world(mission_id, state)
    return state


def add_event(mission_id: UUID, event_type: str, message: str, payload: dict[str, Any]) -> dict[str, Any]:
    key = str(mission_id)
    if using_memory():
        row = {
            "id": _memory["event_id"],
            "mission_id": key,
            "type": event_type,
            "message": message,
            "payload": payload,
            "created_at": _now(),
        }
        _memory["event_id"] += 1
        _memory["events"].append(row)
        return row
    inserted = (
        client()
        .table("agent_events")
        .insert({"mission_id": key, "type": event_type, "message": message, "payload": payload})
        .execute()
    )
    return inserted.data[0]


def set_character(user_id: UUID, mood: str, animation: str, speech: str) -> None:
    row = {
        "user_id": str(user_id),
        "mood": mood,
        "animation": animation,
        "speech": speech,
        "updated_at": _now(),
    }
    if using_memory():
        _memory["character"][row["user_id"]] = row
        return
    client().table("character_state").upsert(row).execute()


def update_concept_status(concept_id: str, status: str) -> None:
    if using_memory():
        for row in _memory["concepts"]:
            if row["id"] == concept_id:
                row["status"] = status
        return
    client().table("concepts").update({"status": status}).eq("id", concept_id).execute()


def _ensure_character(user_id: str) -> None:
    if using_memory():
        _memory["character"].setdefault(
            user_id,
            {
                "user_id": user_id,
                "mood": "calm",
                "animation": "idle_sit",
                "speech": "",
                "updated_at": _now(),
            },
        )
        return
    existing = client().table("character_state").select("user_id").eq("user_id", user_id).limit(1).execute()
    if not existing.data:
        client().table("character_state").insert(
            {"user_id": user_id, "mood": "calm", "animation": "idle_sit", "speech": ""}
        ).execute()


def get_character(user_id: str) -> dict[str, Any] | None:
    _probe()
    if _use_memory:
        return copy.deepcopy(_memory["character"].get(user_id))
    rows = client().table("character_state").select("*").eq("user_id", user_id).limit(1).execute().data
    return rows[0] if rows else None


def mission_user_id(mission_id: UUID) -> UUID:
    bundle = get_bundle(mission_id)
    if bundle is None:
        return DEMO_USER_ID
    return UUID(str(bundle["mission"]["user_id"]))
