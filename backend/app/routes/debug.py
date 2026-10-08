from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.uia import actions, snapshot

router = APIRouter(prefix="/debug", tags=["debug"])


class ActBody(BaseModel):
    action: str
    element_id: str | None = None
    text: str | None = None
    keys: str | None = None
    direction: str | None = "down"
    name: str | None = None


@router.get("/uia/snapshot")
def uia_snapshot() -> dict[str, Any]:
    window = snapshot.get_active_window()
    elements = snapshot.capture_tree(window)
    return {
        "ok": True,
        "window": window,
        "compact": snapshot.compact_for_llm(elements),
        "element_count": len(elements.elements),
    }


@router.post("/uia/act")
def uia_act(body: ActBody) -> dict[str, Any]:
    # IDs can be reused between snapshots, so debug callers must echo the visible name they saw.
    observed = snapshot.capture_tree(snapshot.get_active_window())
    row = observed.element_row(body.element_id or "")
    if body.action in {"click", "type", "scroll"}:
        if row is None or not body.name or body.name != row.get("name"):
            return {"ok": False, "detail": "A current element ID and its exact visible name are required"}
    expected_name = body.name
    if body.action == "click" and body.element_id:
        return actions.click(body.element_id, expected_name=expected_name, observed=observed)
    if body.action == "type" and body.element_id:
        return actions.type_text(body.element_id, body.text or "", expected_name=expected_name, observed=observed)
    if body.action == "press":
        return actions.press_keys(body.keys or "{ENTER}", observed=observed)
    if body.action == "scroll" and body.element_id:
        return actions.scroll(body.element_id, body.direction or "down", expected_name=expected_name, observed=observed)
    if body.action == "focus":
        return actions.focus_window(body.name or "")
    if body.action == "wait" and body.name:
        return actions.wait_for(body.name)
    return {"ok": False, "detail": f"Unknown action {body.action}"}
