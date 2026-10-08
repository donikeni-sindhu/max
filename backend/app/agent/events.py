from typing import Any
from uuid import UUID

from app import db

ANIMATION_FOR_EVENT = {
    "goal_detected": "perk_up",
    "searching": "walk_to_edge",
    "paper_found": "jump_happy",
    "analyzing": "think",
    "prereqs_found": "lightbulb",
    "researching": "dig",
    "ui_observed": "think",
    "ui_action": "point",
    "confirm_needed": "perk_up",
    "path_ready": "celebrate",
    "waiting": "idle_sit",
    "error": "confused",
}

MOOD_FOR_EVENT = {
    "error": "confused",
    "path_ready": "happy",
    "paper_found": "happy",
    "confirm_needed": "alert",
}


def emit(mission_id: UUID, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
    body = payload or {}
    try:
        db.add_event(mission_id, event_type, message, body)
        animation = ANIMATION_FOR_EVENT.get(event_type, "idle_sit")
        mood = MOOD_FOR_EVENT.get(event_type, "calm")
        db.set_character(db.mission_user_id(mission_id), mood, animation, message)
    except Exception as exc:
        print(f"emit failed: {exc}")
