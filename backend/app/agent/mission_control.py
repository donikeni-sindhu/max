"""Per-mission guards shared by the orchestrator, browser driver, and UI actions."""

from __future__ import annotations

import threading
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from app.config import get_settings


class MissionCancelled(Exception):
    """Raised between steps so cancellation prevents any further external UI action."""


@dataclass
class MissionControl:
    # One lock protects the mutable sets and counters while observer and worker threads share them.
    state_lock: threading.RLock = field(default_factory=threading.RLock)
    run_lock: threading.Lock = field(default_factory=threading.Lock)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    visited_urls: set[str] = field(default_factory=set)
    visited_apps: set[str] = field(default_factory=set)
    action_count: int = 0
    failure_reported: bool = False
    target_window: dict[str, object] = field(default_factory=dict)


_controls: dict[str, MissionControl] = {}
_controls_lock = threading.Lock()


def _control(mission_id: UUID | str) -> MissionControl:
    # Keep state by mission ID so replay cannot forget URLs already opened or reset its action budget.
    key = str(mission_id)
    with _controls_lock:
        return _controls.setdefault(key, MissionControl())


def reserve_run(mission_id: UUID | str) -> bool:
    state = _control(mission_id)
    # Non-blocking acquisition prevents a replay request from starting a second worker for the same mission.
    if not state.run_lock.acquire(blocking=False):
        return False
    state.cancel_event.clear()
    return True


def release_run(mission_id: UUID | str) -> None:
    state = _control(mission_id)
    if state.run_lock.locked():
        state.run_lock.release()


def is_running(mission_id: UUID | str) -> bool:
    return _control(mission_id).run_lock.locked()


def remember_target_window(mission_id: UUID | str, window: dict[str, object]) -> None:
    """Pin the user's chosen desktop window to a command so widget focus cannot redirect later actions."""

    if not window.get("hwnd"):
        return
    state = _control(mission_id)
    with state.state_lock:
        state.target_window = dict(window)


def target_window(mission_id: UUID | str) -> dict[str, object]:
    """Return a copy of the recorded window identity for safe foreground fallback during the run."""

    state = _control(mission_id)
    with state.state_lock:
        return dict(state.target_window)


def cancel(mission_id: UUID | str) -> bool:
    state = _control(mission_id)
    # Do not leave cancellation set for a mission that has no worker to observe it.
    if not state.run_lock.locked():
        return False
    state.cancel_event.set()
    return True


def is_cancelled(mission_id: UUID | str) -> bool:
    return _control(mission_id).cancel_event.is_set()


def check_cancelled(mission_id: UUID | str) -> None:
    # Raising at every phase boundary stops the run before another browser or UI side effect.
    if is_cancelled(mission_id):
        raise MissionCancelled("Mission was cancelled")


def wait_or_cancel(mission_id: UUID | str, seconds: float) -> bool:
    # Waiting on the shared event wakes immediately when the UI requests cancellation.
    return _control(mission_id).cancel_event.wait(seconds)


def _report_action_limit(mission_id: UUID | str) -> None:
    # Persist the reason once so a runaway command loop fails visibly instead of timing out silently.
    state = _control(mission_id)
    with state.state_lock:
        if state.failure_reported:
            return
        state.failure_reported = True
    try:
        from app import db
        from app.agent.events import emit

        key = UUID(str(mission_id))
        db.update_mission(key, status="failed")
        emit(key, "error", "Stopped because this mission reached its UI action limit", {"limit": get_settings().max_actions_per_mission})
    except Exception:
        # A DB outage must not permit additional UI actions after the cap.
        pass


def authorize_action(mission_id: UUID | None) -> tuple[bool, str]:
    if mission_id is None:
        return True, ""
    state = _control(mission_id)
    with state.state_lock:
        if state.cancel_event.is_set():
            return False, "Mission was cancelled"
        limit = max(1, get_settings().max_actions_per_mission)
        if state.action_count >= limit:
            state.cancel_event.set()
            over_limit = True
        else:
            state.action_count += 1
            return True, ""
    if over_limit:
        _report_action_limit(mission_id)
        return False, f"Mission action limit reached ({limit})"
    return False, "Mission action was not authorized"


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    # Fragments do not load a new document, so strip them when comparing whether a URL was already visited.
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


def reserve_url(mission_id: UUID | None, url: str) -> tuple[bool, str]:
    if mission_id is None:
        return True, ""
    allowed, detail = authorize_action(mission_id)
    if not allowed:
        return False, detail
    state = _control(mission_id)
    canonical = _canonical_url(url)
    with state.state_lock:
        if state.cancel_event.is_set():
            return False, "Mission was cancelled"
        if canonical in state.visited_urls:
            repeated = True
        else:
            # Reserve before touching the browser so concurrent workers cannot open the same URL twice.
            state.visited_urls.add(canonical)
            repeated = False
    if repeated:
        try:
            from app.agent.events import emit

            emit(UUID(str(mission_id)), "url_skipped", "Skipped a URL this mission already opened", {"url": url})
        except Exception:
            pass
        return False, "Skipped a URL this mission already opened"
    return True, ""


def reserve_app(mission_id: UUID | None, app_name: str) -> tuple[bool, str]:
    """Reserve one normalized app launch per mission so a replan cannot open the same app twice."""

    if mission_id is None:
        return True, ""
    state = _control(mission_id)
    canonical = " ".join(re.findall(r"[a-z0-9]+", app_name.casefold()))
    with state.state_lock:
        if state.cancel_event.is_set():
            return False, "Mission was cancelled"
        if canonical in state.visited_apps:
            return False, f"Skipped {app_name}: this app was already attempted in the mission"
        state.visited_apps.add(canonical)
    return True, ""
