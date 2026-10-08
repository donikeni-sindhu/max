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
        "element_count": len(elements),
    }


@router.post("/uia/act")
def uia_act(body: ActBody) -> dict[str, Any]:
    if body.action == "click" and body.element_id:
        return actions.click(body.element_id)
    if body.action == "type" and body.element_id:
        return actions.type_text(body.element_id, body.text or "")
    if body.action == "press":
        return actions.press_keys(body.keys or "{ENTER}")
    if body.action == "scroll" and body.element_id:
        return actions.scroll(body.element_id, body.direction or "down")
    if body.action == "focus":
        return actions.focus_window(body.name or "")
    if body.action == "wait" and body.name:
        return actions.wait_for(body.name)
    return {"ok": False, "detail": f"Unknown action {body.action}"}
