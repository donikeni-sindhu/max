"""Observe, ask Claude for one UI action, perform it, then check the screen again."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt

from app.agent.events import emit
from app.agent.fallback import browser as playwright_browser
from app.agent.uia import actions, snapshot
from app.config import get_settings


class UiDecision(BaseModel):
    action: Literal["click", "type", "press", "scroll", "done", "fail"]
    element_id: str | None = None
    text: str | None = None
    keys: str | None = None
    reason: str = ""


def _ask(goal: str, compact: str) -> UiDecision:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        "You control a Windows app through UI Automation ids. "
        "Reply with strict JSON only: "
        '{"action":"click|type|press|scroll|done|fail","element_id":"e1","text":"","keys":"","reason":""}. '
        f"Goal: {goal}\nUI:\n{compact}"
    )
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if getattr(block, "text", ""))
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return JSON")
    return UiDecision.model_validate(json.loads(text[start : end + 1]))


def _perform(decision: UiDecision, mission_id: UUID) -> dict[str, Any]:
    if decision.action == "click" and decision.element_id:
        return actions.click(decision.element_id, mission_id)
    if decision.action == "type" and decision.element_id:
        return actions.type_text(decision.element_id, decision.text or "", True, mission_id)
    if decision.action == "press":
        return actions.press_keys(decision.keys or "{ENTER}", mission_id)
    if decision.action == "scroll" and decision.element_id:
        return actions.scroll(decision.element_id, "down", mission_id)
    if decision.action == "done":
        return {"ok": True, "detail": decision.reason or "done"}
    return {"ok": False, "detail": decision.reason or "fail"}


@retry(stop=stop_after_attempt(2), reraise=True)
def _attempt(goal: str, mission_id: UUID) -> dict[str, Any]:
    for _ in range(6):
        window = snapshot.get_active_window()
        elements = snapshot.capture_tree(window)
        compact = snapshot.compact_for_llm(elements)
        decision = _ask(goal, compact)
        result = _perform(decision, mission_id)
        emit(mission_id, "ui_action", result["detail"], {"action": decision.action, "reason": decision.reason})
        if decision.action in {"done", "fail"} or not result["ok"]:
            return result
        snapshot.capture_tree(snapshot.get_active_window())
    return {"ok": False, "detail": "Stopped after 6 UI steps"}


def run_step(goal: str, mission_id: UUID) -> dict[str, Any]:
    try:
        return _attempt(goal, mission_id)
    except (RuntimeError, ValidationError, ValueError, Exception) as exc:
        if get_settings().demo_mode:
            fallback = playwright_browser.search(goal)
            if fallback.get("ok"):
                return fallback
            return {"ok": False, "detail": f"UIA step failed: {exc}", "demo": True}
        return {"ok": False, "detail": str(exc)}
