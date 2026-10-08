"""Plan short UIA actions from fresh snapshots and feed failures back into the next decision."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app import db
from app.agent import apps, llm, mission_control
from app.agent.events import emit
from app.agent.uia import actions, snapshot
from app.config import get_settings

_logger = logging.getLogger(__name__)
_HISTORY_LIMIT = 8


class UiDecision(BaseModel):
    """Constrain model output to actions supported by the UIA action layer."""

    action: Literal["click", "type", "press", "scroll", "launch_app", "done", "fail"]
    element_id: str | None = None
    element_name: str | None = None
    element_type: str | None = None
    app_name: str | None = None
    text: str | None = None
    keys: str | None = None
    clear_first: bool = True
    reason: str = ""


def _ask(
    goal: str,
    observed: snapshot.Snapshot,
    history: list[dict[str, Any]],
    strategies_tried: list[str],
) -> UiDecision:
    """Give the model the current target, allowed operations, recent outcomes, and app-launch escape route."""

    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set; UI commands need a configured action model")
    window = observed.window
    recent = history[-_HISTORY_LIMIT:]
    prompt = (
        "Control the recorded Windows target window with short, visible UIA actions. Return one JSON object with "
        "action click|type|press|scroll|launch_app|done|fail; fields element_id, element_name, element_type, "
        "app_name, text, keys, clear_first, reason. Use only visible element IDs from this snapshot. "
        "Allowed keys use pywinauto syntax such as ^l, {ENTER}, and {VK_LWIN}. Never invent an element ID. "
        "If the requested app is not visible, prefer launch_app with its plain app name rather than hunting. "
        "Use done only after the requested outcome is visible; use fail only to explain a blocked route. "
        f"Goal: {goal}\nActive window title: {window.get('title', '')}\n"
        f"Active window process: {window.get('process', '')}\n"
        f"Strategies already tried: {strategies_tried or 'none'}\n"
        f"Recent action history: {recent}\nVisible UI elements:\n{snapshot.compact_for_llm(observed)}"
    )
    return llm.complete_json(prompt, UiDecision, max_output_tokens=600)


def _resolve_choice(decision: UiDecision, chosen_from: snapshot.Snapshot, latest: snapshot.Snapshot) -> UiDecision:
    """Translate a model-selected old ID into a unique ID from the post-LLM snapshot by stable properties."""

    if decision.action not in {"click", "type", "scroll"}:
        return decision
    old_row = chosen_from.element_row(decision.element_id or "")
    if old_row is None:
        return decision.model_copy(update={"element_id": None, "reason": decision.reason or "The selected element was not in the prompt snapshot"})
    wanted_name = decision.element_name or str(old_row.get("name") or "")
    wanted_type = decision.element_type or str(old_row.get("control_type") or "")
    matches = [
        row
        for row in latest.elements
        if row.get("name") == wanted_name
        and row.get("control_type") == wanted_type
        and row.get("automation_id") == old_row.get("automation_id")
    ]
    if len(matches) != 1:
        # Missing or duplicate identities become a structured failure that the next model turn can recover from.
        return decision.model_copy(update={"element_id": None, "reason": f"stale_element: {wanted_name} ({wanted_type}) no longer resolves uniquely"})
    current = matches[0]
    return decision.model_copy(update={"element_id": str(current["id"]), "element_name": str(current["name"]), "element_type": str(current["control_type"])})


def _observe(
    goal: str,
    mission_id: UUID,
    history: list[dict[str, Any]] | None = None,
    strategies_tried: list[str] | None = None,
) -> tuple[UiDecision, snapshot.Snapshot]:
    """Capture before asking, then capture again after the model call so no ID survives the call."""

    mission_control.check_cancelled(mission_id)
    recorded = mission_control.target_window(mission_id)
    target_hwnd = int(recorded.get("hwnd") or 0)
    window = snapshot.get_active_window(target_hwnd or None)
    if not window.get("hwnd"):
        raise RuntimeError("No visible target window is available; focus the app you want REBORN to control")
    mission_control.remember_target_window(mission_id, window)
    chosen_from = snapshot.capture_tree(window)
    decision = _ask(goal, chosen_from, history or [], strategies_tried or [])
    mission_control.check_cancelled(mission_id)
    latest = snapshot.capture_tree(dict(chosen_from.window))
    resolved = _resolve_choice(decision, chosen_from, latest)
    return resolved, latest


def _perform(decision: UiDecision, mission_id: UUID, observed: snapshot.Snapshot) -> dict[str, Any]:
    """Execute one decision through guarded actions or the general-purpose installed-app launcher."""

    if decision.action in {"click", "type", "scroll"} and not decision.element_id:
        return {"ok": False, "error": "stale_element", "detail": decision.reason or "The chosen UI element disappeared"}
    if decision.action == "click" and decision.element_id:
        return actions.click(decision.element_id, mission_id, expected_name=decision.element_name, observed=observed)
    if decision.action == "type" and decision.element_id:
        return actions.type_text(
            decision.element_id,
            decision.text or "",
            True,
            mission_id,
            decision.element_name,
            observed,
            clear_first=decision.clear_first,
        )
    if decision.action == "press":
        if not decision.keys or not decision.keys.strip():
            return {"ok": False, "error": "missing_keys", "detail": "The model selected press without specifying keys"}
        return actions.press_keys(decision.keys, mission_id, observed=observed)
    if decision.action == "scroll" and decision.element_id:
        return actions.scroll(decision.element_id, "down", mission_id, decision.element_name, observed)
    if decision.action == "launch_app":
        from app.agent.launcher import launch_app

        app_name = (decision.app_name or decision.text or "").strip()
        if not app_name:
            return {"ok": False, "error": "missing_app_name", "detail": "The model selected launch_app without naming an app"}
        launched = launch_app(app_name, mission_id)
        return {"ok": bool(launched.get("ok")), "detail": launched.get("detail", ""), "error": launched.get("error"), "launch": launched}
    if decision.action == "done":
        return {"ok": True, "detail": decision.reason or "The requested outcome is visible"}
    return {"ok": False, "error": "model_failed", "detail": decision.reason or "The action model could not complete the command"}


def _target(decision: UiDecision, observed: snapshot.Snapshot) -> dict[str, str]:
    """Describe the chosen control for history without copying its ephemeral numeric ID."""

    row = observed.element_row(decision.element_id or "")
    if row:
        return {"name": str(row.get("name") or ""), "type": str(row.get("control_type") or "")}
    return {"name": decision.app_name or decision.element_name or "", "type": decision.action}


def _record_history(
    history: list[dict[str, Any]],
    step: int,
    decision: UiDecision,
    observed: snapshot.Snapshot,
    result: dict[str, Any],
) -> None:
    """Store structured outcomes so the next model turn can recover from the exact failed action."""

    history.append(
        {
            "step": step,
            "action": decision.action,
            "target": _target(decision, observed),
            "result": str(result.get("detail") or ""),
            "error": str(result.get("error") or ("" if result.get("ok") else result.get("detail") or "failed")),
        }
    )


def _log_action(mission_id: UUID, decision: UiDecision, result: dict[str, Any]) -> None:
    """Publish the result and target as an event so the widget can show replans and failures."""

    emit(
        mission_id,
        "ui_action",
        str(result.get("detail") or "UI action finished"),
        {
            "ok": result.get("ok", False),
            "error": result.get("error"),
            "action": decision.action,
            "element_id": decision.element_id,
            "element_name": decision.element_name,
            "element_type": decision.element_type,
            "app_name": decision.app_name,
            "reason": decision.reason,
        },
    )


def run_step(goal: str, mission_id: UUID) -> dict[str, Any]:
    """Run one plan-and-act cycle while allowing transport and response errors to reach the mission boundary."""

    try:
        decision, observed = _observe(goal, mission_id)
    except (RuntimeError, ValidationError) as exc:
        _logger.exception("Could not prepare one UI action for mission %s", mission_id)
        return {"ok": False, "detail": str(exc), "error": "planning_failed"}
    result = _perform(decision, mission_id, observed)
    if decision.action not in {"done", "fail"} or not result.get("ok"):
        _log_action(mission_id, decision, result)
    return result


def run_command(goal: str, mission_id: UUID) -> dict[str, str]:
    """Keep replanning after errors, but stop after the configured budget or three identical choices."""

    limit = max(1, get_settings().max_actions_per_mission)
    history: list[dict[str, Any]] = []
    strategies_tried: list[str] = []
    repeated: Counter[tuple[str, str, str]] = Counter()
    for step in range(limit):
        mission_control.check_cancelled(mission_id)
        try:
            decision, observed = _observe(goal, mission_id, history, strategies_tried)
        except (RuntimeError, ValidationError) as exc:
            # A malformed or unavailable plan cannot produce a safe action; preserve the concrete reason.
            _logger.exception("UI plan failed for mission %s", mission_id)
            raise RuntimeError(str(exc)) from exc
        result = _perform(decision, mission_id, observed)
        _record_history(history, step + 1, decision, observed, result)
        _log_action(mission_id, decision, result)
        launch = result.get("launch") or {}
        launch_attempts = launch.get("attempts") or (launch.get("evidence") or {}).get("attempts", [])
        for attempt in launch_attempts:
            strategy = str(attempt.get("strategy") or "")
            if strategy and strategy not in strategies_tried:
                strategies_tried.append(strategy)
        if decision.action == "done" and result.get("ok"):
            emit(mission_id, "command_done", str(result["detail"]), {"goal": goal, "steps": step})
            db.update_mission(mission_id, status="complete")
            return {"status": "complete", "detail": str(result["detail"])}
        if result.get("ok") and decision.action == "launch_app":
            emit(mission_id, "command_done", str(result["detail"]), {"goal": goal, "steps": step + 1})
            db.update_mission(mission_id, status="complete")
            return {"status": "complete", "detail": str(result["detail"])}
        signature = (
            decision.action,
            str(decision.element_name or decision.app_name or "").casefold(),
            str(decision.keys or decision.text or decision.element_type or "").casefold(),
        )
        repeated[signature] += 1
        if repeated[signature] >= 3:
            detail = f"Stopped after the same {decision.action} choice repeated three times: {result.get('detail', '')}"
            emit(mission_id, "error", detail, {"history": history[-_HISTORY_LIMIT:]})
            raise RuntimeError(detail)
        if not result.get("ok"):
            # The next _ask receives the exact structured error so it can choose another route.
            emit(mission_id, "ui_replan", f"Action failed; replanning: {result.get('detail', 'unknown error')}", {"history": history[-_HISTORY_LIMIT:]})
        mission_control.check_cancelled(mission_id)
    detail = f"Stopped after reaching the {limit}-step command limit"
    emit(mission_id, "error", detail, {"history": history[-_HISTORY_LIMIT:]})
    raise RuntimeError(detail)


def launch_via_ui_element(app_name: str, mission_id: UUID | None = None) -> dict[str, Any]:
    """Search only taskbar, desktop, and currently visible Start/search UIA surfaces for a launch control."""

    try:
        import win32gui
        from pywinauto import Desktop
    except ImportError as exc:
        return {"ok": False, "detail": f"UI Automation is unavailable: {exc}"}
    wanted = apps.lookup(app_name)
    labels = [app_name, *(wanted.aliases if wanted else ())]
    if wanted:
        labels.append(wanted.name)
    candidates: list[int] = []

    def collect(hwnd: int, _: object) -> None:
        title = win32gui.GetWindowText(hwnd).casefold()
        class_name = win32gui.GetClassName(hwnd).casefold()
        # These shell surfaces are the only places where clicking is treated as app launch, not general interaction.
        if class_name in {"shell_traywnd", "progman", "workerw"} or any(word in title for word in ("start", "search")):
            if snapshot.is_window_visible(hwnd):
                candidates.append(hwnd)

    try:
        with snapshot.com_initialized(), snapshot.UIA_LOCK:
            win32gui.EnumWindows(collect, None)
            for hwnd in candidates:
                root = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
                queue: list[tuple[Any, int]] = [(root, 0)]
                visited = 0
                while queue and visited < 500:
                    control, depth = queue.pop(0)
                    visited += 1
                    try:
                        name = str(control.element_info.name or "").strip()
                        control_type = str(control.element_info.control_type or "")
                        match = any(
                            label.casefold() == name.casefold() or
                            (len(label) >= 3 and label.casefold() in name.casefold())
                            for label in labels
                        )
                        if match and control_type in {"Button", "ListItem", "MenuItem", "TreeItem"}:
                            try:
                                control.invoke()
                            except (AttributeError, OSError, RuntimeError):
                                control.click_input()
                            evidence = {"name": name, "control_type": control_type, "hwnd": int(control.element_info.handle or hwnd)}
                            return {"ok": True, "detail": f"Clicked {name}", "evidence": evidence}
                    except (AttributeError, OSError, RuntimeError):
                        pass
                    if depth < 8:
                        try:
                            queue.extend((child, depth + 1) for child in control.children())
                        except (AttributeError, OSError, RuntimeError):
                            pass
    except (OSError, RuntimeError) as exc:
        return {"ok": False, "detail": f"Could not inspect shell UI: {exc}"}
    return {"ok": False, "detail": f"No clickable taskbar, desktop, or Start element matched {app_name}"}
