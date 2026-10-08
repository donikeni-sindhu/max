"""Allowlist, password refusal, and confirm-before-sensitive-click."""

from __future__ import annotations

import time
from threading import Event
from uuid import UUID

from app.config import get_settings

_pending: dict[str, Event] = {}
_answers: dict[str, bool] = {}
_last_action = 0.0
SENSITIVE_WORDS = ("delete", "uninstall", "send", "pay", "purchase", "submit")


def allowed_process(process_name: str) -> bool:
    return process_name.lower() in get_settings().allowed_app_names()


def is_password(name: str, automation_id: str) -> bool:
    blob = f"{name} {automation_id}".lower()
    return "password" in blob or "passwd" in blob


def needs_confirm(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in SENSITIVE_WORDS)


def pace() -> None:
    global _last_action
    wait = 0.3 - (time.monotonic() - _last_action)
    if wait > 0:
        time.sleep(wait)
    _last_action = time.monotonic()


def request_confirm(mission_id: UUID, detail: str) -> bool:
    from app.agent.events import emit

    key = str(mission_id)
    event = Event()
    _pending[key] = event
    emit(mission_id, "confirm_needed", detail, {"pending": True})
    event.wait(timeout=120)
    return _answers.pop(key, False)


def resolve_confirm(mission_id: UUID, approved: bool) -> None:
    key = str(mission_id)
    _answers[key] = approved
    event = _pending.pop(key, None)
    if event is not None:
        event.set()


def guard_action(process_name: str, name: str, automation_id: str, mission_id: UUID | None) -> dict[str, object] | None:
    if not allowed_process(process_name):
        return {"ok": False, "detail": f"Refused app {process_name or 'unknown'}"}
    if is_password(name, automation_id):
        return {"ok": False, "detail": "Refused password field"}
    if needs_confirm(name):
        if mission_id is None:
            return {"ok": False, "detail": f"Needs confirmation: {name}"}
        approved = request_confirm(mission_id, f"Allow action on '{name}'?")
        if not approved:
            return {"ok": False, "detail": f"Rejected action on {name}"}
    return None
