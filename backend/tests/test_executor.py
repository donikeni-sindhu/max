"""Executor loop tests use immutable fake snapshots and never call Windows UI Automation."""

from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agent.uia import executor
from app.agent.uia.snapshot import Snapshot


def _snapshot(name: str = "Save", element_id: str = "e1") -> Snapshot:
    """Build a tiny immutable prompt snapshot with a stable button identity."""

    row = MappingProxyType({"id": element_id, "name": name, "control_type": "Button", "automation_id": name.casefold()})
    return Snapshot(
        MappingProxyType({"title": "Example", "process": "chrome.exe", "hwnd": 123}),
        (row,),
        MappingProxyType({element_id: object()}),
        1,
        1.0,
    )


def test_choice_from_old_snapshot_is_re_resolved_by_name_and_type():
    """A changed numeric ID remains safe when the same stable element can be found in the fresh capture."""

    old = _snapshot("Save", "e1")
    current = _snapshot("Save", "e9")
    decision = executor.UiDecision(action="click", element_id="e1", element_name="Save", element_type="Button")
    resolved = executor._resolve_choice(decision, old, current)
    assert resolved.element_id == "e9"


def test_choice_that_changes_identity_becomes_a_stale_element_failure():
    """A reused ID pointing to another control is discarded before any click can occur."""

    old = _snapshot("Save", "e1")
    changed = _snapshot("Delete", "e1")
    decision = executor.UiDecision(action="click", element_id="e1", element_name="Save", element_type="Button")
    resolved = executor._resolve_choice(decision, old, changed)
    assert resolved.element_id is None
    result = executor._perform(resolved, uuid4(), changed)
    assert result["error"] == "stale_element"


def test_failed_action_error_is_sent_to_the_next_model_turn():
    """The loop passes the previous structured error into the following prompt before replanning."""

    mission_id = uuid4()
    observed = _snapshot()
    seen_histories = []

    def observe(goal, mission, history=None, strategies=None):
        seen_histories.append(list(history or []))
        if len(seen_histories) == 1:
            return executor.UiDecision(action="click", element_id="e1", element_name="Save", element_type="Button"), observed
        return executor.UiDecision(action="done", reason="The requested result is visible"), observed

    with (
        patch.object(executor, "_observe", side_effect=observe),
        patch.object(executor, "_perform", side_effect=[{"ok": False, "error": "stale_element", "detail": "control disappeared"}, {"ok": True, "detail": "done"}]),
        patch.object(executor, "_log_action"),
        patch("app.agent.uia.executor.emit"),
        patch("app.agent.uia.executor.db.update_mission"),
    ):
        result = executor.run_command("click Save", mission_id)

    assert result["status"] == "complete"
    assert seen_histories[1][0]["error"] == "stale_element"
    assert seen_histories[1][0]["result"] == "control disappeared"


def test_three_identical_failed_actions_stop_the_loop():
    """Repeated choices stop after three attempts instead of consuming the full mission budget."""

    mission_id = uuid4()
    observed = _snapshot()
    decision = executor.UiDecision(action="click", element_id="e1", element_name="Save", element_type="Button")
    with (
        patch.object(executor, "_observe", return_value=(decision, observed)),
        patch.object(executor, "_perform", return_value={"ok": False, "error": "stale_element", "detail": "still missing"}),
        patch.object(executor, "_log_action"),
        patch("app.agent.uia.executor.emit"),
        patch("app.agent.uia.executor.get_settings", return_value=SimpleNamespace(max_actions_per_mission=25)),
    ):
        with pytest.raises(RuntimeError, match="repeated three times"):
            executor.run_command("click Save", mission_id)


def test_step_cap_stops_distinct_actions():
    """Different successful actions still cannot exceed the configured hard step cap."""

    mission_id = uuid4()
    observed = _snapshot()
    choices = iter(
        [
            (executor.UiDecision(action="click", element_id="e1", element_name="Save", element_type="Button"), observed),
            (executor.UiDecision(action="click", element_id="e1", element_name="Delete", element_type="Button"), observed),
        ]
    )
    with (
        patch.object(executor, "_observe", side_effect=lambda *args: next(choices)),
        patch.object(executor, "_perform", return_value={"ok": True, "detail": "clicked"}),
        patch.object(executor, "_log_action"),
        patch("app.agent.uia.executor.emit"),
        patch("app.agent.uia.executor.get_settings", return_value=SimpleNamespace(max_actions_per_mission=2)),
    ):
        with pytest.raises(RuntimeError, match="2-step command limit"):
            executor.run_command("click two controls", mission_id)


def test_press_without_keys_does_not_default_to_enter():
    """An incomplete model decision is rejected so it cannot unexpectedly send a message."""

    decision = executor.UiDecision(action="press")
    result = executor._perform(decision, uuid4(), _snapshot())
    assert result["error"] == "missing_keys"
