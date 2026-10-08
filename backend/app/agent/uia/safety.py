"""Session-scoped interaction approval, sensitive-field blocking, and confirmation for risky actions."""

from __future__ import annotations

import re
import time
from threading import Event, Lock
from uuid import UUID

from app.agent import apps, mission_control
from app.config import get_settings

_pending: dict[str, Event] = {}
_answers: dict[str, bool] = {}
_pending_lock = Lock()
_last_action = 0.0
_CONFIRM_TIMEOUT_SECONDS = 120
_approval_lock = Lock()
_approved_apps: dict[str, str] = {}
_SENSITIVE_PATTERN = re.compile(r"\b(?:delete|uninstall|send|pay|purchase|submit)\b", re.IGNORECASE)
_SENSITIVE_FIELD_PATTERN = re.compile(
    r"\b(?:password|passwd|card(?: number)?|credit card|debit card|cvv|cvc|security code|otp|one[ -]?time (?:code|password)|verification code|pin)\b",
    re.IGNORECASE,
)
_DESTRUCTIVE_SHORTCUTS = {"%{f4}", "^w", "^+w", "{vk_lwin}r", "^+{delete}"}
_MESSAGE_SUBMIT_KEYS = {"{enter}", "^{enter}"}


def _app_label(process_name: str, title: str = "", package: str = "") -> str:
    """Use a friendly registry name when possible so a permission prompt is understandable."""

    spec = apps.identify(process=process_name, title=title, package=package)
    return spec.name if spec else (process_name or package or title or "unknown app")


def _app_key(process_name: str, title: str = "", package: str = "") -> str:
    """Key grants by resolved app identity rather than the temporary ApplicationFrameHost process."""

    label = _app_label(process_name, title, package)
    return apps.normalize_name(package or label)


def allowed_process(process_name: str) -> bool:
    """Check only the no-prompt default policy; user-approved apps live in a separate session set."""

    return process_name.casefold() in get_settings().interact_allowed_app_names()


def approved_apps() -> list[str]:
    """Return friendly names for live session grants so the widget can offer revocation controls."""

    with _approval_lock:
        return sorted(_approved_apps.values(), key=str.casefold)


def revoke_app_approval(app_name: str) -> bool:
    """Remove a session interaction grant immediately when the user revokes it in the widget."""

    normalized = apps.normalize_name(app_name)
    with _approval_lock:
        matching = [key for key, label in _approved_apps.items() if key == normalized or apps.normalize_name(label) == normalized]
        for key in matching:
            _approved_apps.pop(key, None)
    return bool(matching)


def is_password(name: str, automation_id: str, password: bool = False) -> bool:
    """Block UIA password metadata and recognizable card, PIN, OTP, and verification-code fields."""

    return password or bool(_SENSITIVE_FIELD_PATTERN.search(f"{name} {automation_id}"))


def needs_confirm(name: str) -> bool:
    """Use whole words so `Payment history` and `Resend` do not accidentally trigger a confirmation."""

    return bool(_SENSITIVE_PATTERN.search(name))


def pace() -> None:
    """Space native input calls to avoid dropping rapid consecutive UIA operations."""

    global _last_action
    wait = 0.3 - (time.monotonic() - _last_action)
    if wait > 0:
        time.sleep(wait)
    _last_action = time.monotonic()


def request_confirm(mission_id: UUID, detail: str) -> bool:
    """Pause one sensitive action until the widget approves, rejects, times out, or cancels it."""

    from app import db
    from app.agent.events import emit

    key = str(mission_id)
    event = Event()
    with _pending_lock:
        _pending[key] = event
        _answers.pop(key, None)
    # Persist the prompt before announcing it; the widget reads this explicit state directly.
    db.patch_world(mission_id, pending_confirmation=detail)
    emit(mission_id, "confirm_needed", detail, {"pending": True})
    deadline = time.monotonic() + _CONFIRM_TIMEOUT_SECONDS
    timed_out = False
    while not event.is_set():
        if mission_control.is_cancelled(mission_id):
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        # Short event waits keep cancel responsive without polling continuously.
        event.wait(min(0.25, remaining))
    with _pending_lock:
        approved = _answers.pop(key, False)
        _pending.pop(key, None)
    db.patch_world(mission_id, pending_confirmation=None)
    if timed_out:
        emit(mission_id, "confirm_rejected", "Action rejected (timeout)", {"approved": False, "timeout": True})
        return False
    if mission_control.is_cancelled(mission_id):
        emit(mission_id, "confirm_rejected", "Action rejected because the mission was cancelled", {"approved": False, "timeout": False})
        return False
    if not approved:
        emit(mission_id, "confirm_rejected", "Action rejected by the user", {"approved": False, "timeout": False})
    return approved


def resolve_confirm(mission_id: UUID, approved: bool) -> bool:
    """Accept only a currently pending decision so unsolicited approvals cannot authorize future actions."""

    key = str(mission_id)
    with _pending_lock:
        event = _pending.get(key)
        if event is None:
            return False
        _answers[key] = approved
    # Clear the visible dialog before waking the worker that is waiting on this decision.
    from app import db

    db.patch_world(mission_id, pending_confirmation=None)
    event.set()
    return True


def _ensure_interaction_approval(
    process_name: str,
    name: str,
    package: str,
    mission_id: UUID | None,
) -> dict[str, object] | None:
    """Ask once per non-browser app and store only a session-memory grant after explicit approval."""

    normalized_process = process_name.casefold()
    configured = {item.casefold() for item in get_settings().interact_allowed_app_names()}
    if normalized_process in configured:
        return None
    label = _app_label(process_name, name, package)
    key = _app_key(process_name, name, package)
    with _approval_lock:
        if key in _approved_apps:
            return None
    if mission_id is None:
        return {"ok": False, "detail": f"Interaction with {label} needs per-session approval"}
    approved = request_confirm(mission_id, f"Allow REBORN to interact with {label} for this session?")
    if not approved:
        return {"ok": False, "detail": f"Interaction with {label} was not approved"}
    with _approval_lock:
        _approved_apps[key] = label
    return None


def _confirm_if_needed(name: str, mission_id: UUID | None, forced: bool = False) -> dict[str, object] | None:
    """Require a separate per-action confirmation after app access has been approved."""

    if not forced and not needs_confirm(name):
        return None
    if mission_id is None:
        return {"ok": False, "detail": f"Needs confirmation: {name}"}
    if not request_confirm(mission_id, f"Allow action on '{name}'?"):
        return {"ok": False, "detail": f"Rejected action on {name}"}
    return None


def guard_action(
    process_name: str,
    name: str,
    automation_id: str,
    mission_id: UUID | None,
    package: str = "",
    password: bool = False,
    force_confirm: bool = False,
) -> dict[str, object] | None:
    """Apply app approval, credential-field refusal, and risky-action confirmation to the target element."""

    blocked = _ensure_interaction_approval(process_name, name, package, mission_id)
    if blocked:
        return blocked
    if is_password(name, automation_id, password):
        return {"ok": False, "detail": "Refused password, payment-card, PIN, or one-time-code field"}
    return _confirm_if_needed(name, mission_id, force_confirm)


def requires_destructive_shortcut(keys: str) -> bool:
    """Flag only the named destructive pywinauto chords; ordinary navigation keys stay available."""

    normalized = re.sub(r"\s+", "", keys.casefold())
    return normalized in _DESTRUCTIVE_SHORTCUTS


def requires_message_confirmation(process: str, title: str, package: str, keys: str) -> bool:
    """Treat Enter in a registered messaging app as send, including Ctrl+Enter compose conventions."""

    return apps.is_messaging_app(process, title, package) and re.sub(r"\s+", "", keys.casefold()) in _MESSAGE_SUBMIT_KEYS
