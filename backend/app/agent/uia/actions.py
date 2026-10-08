"""UIA actions. Each action is serialized, checked against its source snapshot, and returned as {ok, detail}."""

from __future__ import annotations

import time
from functools import wraps
from typing import Any
from uuid import UUID

from app.agent import mission_control
from app.agent.uia import snapshot
from app.agent.uia.snapshot import Snapshot
from app.agent.uia.safety import guard_action, pace


def _uia_locked(function: Any) -> Any:
    # A single reentrant lock prevents observer tree walks from racing a foreground click or key press.
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        # COM apartments are thread-owned, so each backend worker initializes COM before taking the shared lock.
        with snapshot.com_initialized(), snapshot.UIA_LOCK:
            return function(*args, **kwargs)

    return wrapped


def _result(ok: bool, detail: str, error: str | None = None) -> dict[str, Any]:
    """Return a uniform UI outcome and optionally identify machine-readable recoverable failures."""

    result = {"ok": ok, "detail": detail}
    if error:
        result["error"] = error
    return result


def _log(mission_id: UUID | None, detail: str, ok: bool, context: dict[str, Any] | None = None) -> None:
    """Record action results together with the resolved app identity needed to audit policy decisions."""

    if mission_id is None:
        return
    from app.agent.events import emit

    emit(mission_id, "ui_action", detail, {"ok": ok, **(context or {})})


def _fresh_handle(
    element_id: str,
    observed: Snapshot | None,
    expected_name: str | None,
) -> tuple[Snapshot | None, Any, dict[str, Any] | None]:
    """Re-find a control by stable properties in its source window instead of trusting snapshot IDs."""

    if observed is None:
        return None, None, None
    expected = observed.element_row(element_id)
    if expected is None:
        return None, None, None
    chosen_name = expected_name or str(expected.get("name") or "")
    if chosen_name != expected.get("name"):
        return None, None, None

    # Re-snapshot the recorded HWND immediately before input, even if the widget took foreground meanwhile.
    current = snapshot.capture_tree(dict(observed.window))
    if current.window.get("hwnd") != observed.window.get("hwnd"):
        return current, None, {"error": "stale_element", "detail": f"Stale element {element_id}: its source window is no longer available"}
    matches = [
        row
        for row in current.elements
        if row.get("name") == chosen_name
        and row.get("control_type") == expected.get("control_type")
        and row.get("automation_id") == expected.get("automation_id")
    ]
    if len(matches) > 1:
        matches = [row for row in matches if row.get("rect") == expected.get("rect")]
    if len(matches) != 1:
        return current, None, {"error": "stale_element", "detail": f"Stale element {element_id}: its name, type, or automation ID changed"}
    row = dict(matches[0])
    handle = current.element_handle(str(row["id"]))
    if handle is None:
        return current, None, {"error": "stale_element", "detail": f"Stale element {element_id}: the fresh snapshot has no matching handle"}
    return current, handle, row


def _guard(window: dict[str, Any], row: dict[str, Any], mission_id: UUID | None) -> dict[str, Any] | None:
    """Apply interaction policy to the native window that owns this element, not a foreground lookup."""

    hwnd = int(row.get("hwnd") or window.get("hwnd") or 0)
    target = snapshot.window_context(hwnd) if hwnd else window
    blocked = guard_action(
        str(target.get("process") or window.get("process") or ""),
        str(row.get("name") or ""),
        str(row.get("automation_id") or ""),
        mission_id,
        package=str(target.get("package") or window.get("package") or ""),
        password=bool(row.get("password")),
    )
    if isinstance(blocked, dict):
        return blocked
    row["_target_context"] = target
    return None


def _focus_native(hwnd: int) -> bool:
    """Focus an already-approved target without charging a second action or bypassing its policy check."""

    import ctypes
    import win32con
    import win32gui

    if not hwnd or not snapshot.is_window_visible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    finally:
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    return win32gui.GetForegroundWindow() == hwnd


@_uia_locked
def focus_hwnd(hwnd: int, mission_id: UUID | None = None, launch: bool = False) -> dict[str, Any]:
    """Focus a native window, restoring it only when minimized and distinguishing launch from interaction."""

    try:
        allowed, detail = mission_control.authorize_action(mission_id)
        if not allowed:
            return _result(False, detail)
        import win32gui

        if not hwnd or not snapshot.is_window_visible(hwnd):
            return _result(False, "Window not found")
        target = snapshot.window_context(hwnd)
        # A user-requested app launch may focus any app; later input still goes through interaction approval.
        blocked = None if launch else guard_action(
            str(target.get("process") or ""), "", "", mission_id, package=str(target.get("package") or "")
        )
        if blocked:
            return blocked
        focused = _focus_native(hwnd)
        title = win32gui.GetWindowText(hwnd)
        _log(mission_id, f"Focused {title} ({target.get('process')})", focused)
        return _result(focused, f"Focused {title}" if focused else f"Could not focus {title}")
    except (ImportError, OSError, RuntimeError) as exc:
        return _result(False, str(exc))


@_uia_locked
def focus_window(title: str = "", mission_id: UUID | None = None, launch: bool = False) -> dict[str, Any]:
    """Resolve a visible title match without selecting unrelated windows from enumeration order."""

    try:
        import win32gui

        if not title:
            return focus_hwnd(int(snapshot.get_active_window().get("hwnd") or 0), mission_id, launch=launch)
        found = 0

        def visit(handle: int, _: object) -> None:
            nonlocal found
            text = win32gui.GetWindowText(handle)
            if title.lower() in text.lower() and "reborn" not in text.lower() and snapshot.is_window_visible(handle):
                found = handle

        win32gui.EnumWindows(visit, None)
        return focus_hwnd(found, mission_id, launch=launch)
    except (ImportError, OSError, RuntimeError) as exc:
        return _result(False, str(exc))


@_uia_locked
def click(
    element_id: str,
    mission_id: UUID | None = None,
    expected_name: str | None = None,
    observed: Snapshot | None = None,
) -> dict[str, Any]:
    """Re-resolve, policy-check, and invoke the exact control the model selected."""

    try:
        allowed, detail = mission_control.authorize_action(mission_id)
        if not allowed:
            return _result(False, detail)
        current, handle, row = _fresh_handle(element_id, observed, expected_name)
        if current is None or row is None or handle is None:
            stale = row or {"detail": f"Stale element {element_id}; take a new UI snapshot", "error": "stale_element"}
            return _result(False, str(stale.get("detail")), str(stale.get("error") or "stale_element"))
        blocked = _guard(dict(current.window), row, mission_id)
        if blocked:
            return blocked
        pace()
        try:
            handle.invoke()
            detail = f"Invoked {element_id} {row['name']}"
        except Exception:
            handle.click_input()
            detail = f"Clicked {element_id} {row['name']}"
        _log(mission_id, detail, True, row.get("_target_context"))
        return _result(True, detail)
    except (ImportError, OSError, RuntimeError, AttributeError, ValueError) as exc:
        return _result(False, str(exc))


@_uia_locked
def type_text(
    element_id: str,
    text: str,
    human_delay: bool = True,
    mission_id: UUID | None = None,
    expected_name: str | None = None,
    observed: Snapshot | None = None,
    clear_first: bool = True,
) -> dict[str, Any]:
    """Set or type text, verifying the resulting value because many custom controls ignore ValuePattern."""

    try:
        allowed, detail = mission_control.authorize_action(mission_id)
        if not allowed:
            return _result(False, detail)
        current, handle, row = _fresh_handle(element_id, observed, expected_name)
        if current is None or row is None or handle is None:
            stale = row or {"detail": f"Stale element {element_id}; take a new UI snapshot", "error": "stale_element"}
            return _result(False, str(stale.get("detail")), str(stale.get("error") or "stale_element"))
        blocked = _guard(dict(current.window), row, mission_id)
        if blocked:
            return blocked
        pace()
        expected_value = text if clear_first else f"{row.get('value', '')}{text}"
        try:
            if not clear_first:
                raise AttributeError("Appending uses keyboard input so existing text is preserved")
            handle.iface_value.SetValue(text)
            actual_value = str(handle.iface_value.CurrentValue or "")
        except (AttributeError, OSError, RuntimeError):
            actual_value = ""
        if actual_value != expected_value:
            # Keyboard typing covers controls whose UIA ValuePattern accepts calls but drops their text.
            handle.click_input()
            if clear_first:
                handle.type_keys("^a{BACKSPACE}", set_foreground=True)
            for char in text:
                # Check cancellation between characters so long text entry can stop promptly.
                if mission_id is not None:
                    mission_control.check_cancelled(mission_id)
                handle.type_keys(char, with_spaces=True, pause=0.02 if human_delay else 0)
                if human_delay:
                    time.sleep(0.02)
            try:
                actual_value = str(handle.iface_value.CurrentValue or "")
            except (AttributeError, OSError, RuntimeError):
                actual_value = ""
        if actual_value != expected_value:
            return _result(False, f"Text entry could not be verified in {row['name']}", "value_unverified")
        detail = f"Typed into {element_id} {row['name']}"
        _log(mission_id, detail, True, row.get("_target_context"))
        return _result(True, detail)
    except (ImportError, OSError, RuntimeError, AttributeError, ValueError) as exc:
        return _result(False, str(exc))


@_uia_locked
def press_keys(
    keys: str,
    mission_id: UUID | None = None,
    process_name: str | None = None,
    observed: Snapshot | None = None,
) -> dict[str, Any]:
    """Send a non-empty key sequence only to the run's recorded window after focused-field policy checks."""

    try:
        allowed, detail = mission_control.authorize_action(mission_id)
        if not allowed:
            return _result(False, detail)
        if observed is None or not keys.strip():
            if not keys.strip():
                return _result(False, "No keys were supplied; REBORN will not assume Enter", "missing_keys")
            return _result(False, "A UI snapshot is required before sending keys")
        window = dict(observed.window)
        hwnd = int(window.get("hwnd") or 0)
        if not hwnd:
            return _result(False, "The run has no recorded target window")
        # The refreshed capture supplies the true focused element for Enter/send and password-field checks.
        fresh = snapshot.capture_tree(window)
        focused = next((dict(row) for row in fresh.elements if row.get("focused")), {})
        target_hwnd = int(focused.get("hwnd") or hwnd)
        target = snapshot.window_context(target_hwnd)
        from app.agent.uia import safety

        message_submit = safety.requires_message_confirmation(
            str(target.get("process") or window.get("process") or ""),
            str(window.get("title") or ""),
            str(target.get("package") or window.get("package") or ""),
            keys,
        )
        destructive = safety.requires_destructive_shortcut(keys)
        focused_name = str(focused.get("name") or "")
        # Check the focused control's own label so Enter on a focused Send button needs approval too.
        confirm_target = (
            "Send message" if message_submit else
            focused_name if safety.needs_confirm(focused_name) else
            f"Destructive shortcut {keys}" if destructive else keys
        )
        blocked = guard_action(
            str(target.get("process") or window.get("process") or ""),
            confirm_target,
            str(focused.get("automation_id") or ""),
            mission_id,
            package=str(target.get("package") or window.get("package") or ""),
            password=bool(focused.get("password")),
            force_confirm=message_submit or destructive,
        )
        if blocked:
            return blocked
        import win32gui

        foreground = int(win32gui.GetForegroundWindow() or 0)
        if foreground != hwnd:
            foreground_title = win32gui.GetWindowText(foreground) if foreground else ""
            # When the transparent widget owns focus, return to this run's pinned target instead of guessing.
            if "reborn" not in foreground_title.casefold() or not _focus_native(hwnd):
                return _result(False, "The target window is no longer focused; select it and try again", "target_not_focused")
        if int(win32gui.GetForegroundWindow() or 0) != hwnd:
            return _result(False, "Could not focus the recorded target window", "target_not_focused")
        from pywinauto.keyboard import send_keys

        pace()
        send_keys(keys.strip(), pause=0.05)
        detail = f"Pressed {keys}"
        _log(mission_id, detail, True, {"process": target.get("process"), "package": target.get("package"), "hwnd": hwnd})
        return _result(True, detail)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return _result(False, str(exc))


@_uia_locked
def select_tab(name: str, mission_id: UUID | None = None) -> dict[str, Any]:
    """Choose a tab by its visible label from one capture and pass that exact capture to click."""

    try:
        observed = snapshot.capture_tree(snapshot.get_active_window())
        match = next(
            (
                element
                for element in observed.elements
                if element["control_type"] == "TabItem" and name.lower() in element["name"].lower()
            ),
            None,
        )
        if match is None:
            return _result(False, f"Tab not found: {name}")
        return click(str(match["id"]), mission_id, str(match["name"]), observed)
    except Exception as exc:
        return _result(False, str(exc))


@_uia_locked
def scroll(
    element_id: str,
    direction: str,
    mission_id: UUID | None = None,
    expected_name: str | None = None,
    observed: Snapshot | None = None,
) -> dict[str, Any]:
    """Scroll a re-resolved element and report stale or blocked targets without raising into the mission loop."""

    try:
        allowed, detail = mission_control.authorize_action(mission_id)
        if not allowed:
            return _result(False, detail)
        current, handle, row = _fresh_handle(element_id, observed, expected_name)
        if current is None or row is None or handle is None:
            stale = row or {"detail": f"Stale element {element_id}; take a new UI snapshot", "error": "stale_element"}
            return _result(False, str(stale.get("detail")), str(stale.get("error") or "stale_element"))
        blocked = _guard(dict(current.window), row, mission_id)
        if blocked:
            return blocked
        pace()
        amount = 3 if direction.lower() != "up" else -3
        try:
            handle.scroll(direction, amount)
        except Exception:
            from pywinauto.keyboard import send_keys

            handle.set_focus()
            send_keys("{PGDN}" if amount > 0 else "{PGUP}")
        detail = f"Scrolled {direction} on {row['name']}"
        _log(mission_id, detail, True, row.get("_target_context"))
        return _result(True, detail)
    except Exception as exc:
        return _result(False, str(exc))


@_uia_locked
def wait_for(element_name: str, timeout: float = 10) -> dict[str, Any]:
    """Poll immutable captures for a named control without keeping a shared element-ID registry."""

    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            observed = snapshot.capture_tree()
            found = next(
                (element for element in observed.elements if element_name.lower() in element["name"].lower()),
                None,
            )
            if found:
                return _result(True, f"Found {found['id']} {found['name']}")
            time.sleep(0.4)
        return _result(False, f"Timed out waiting for {element_name}")
    except Exception as exc:
        return _result(False, str(exc))
