"""UIA actions. Each call returns {ok, detail} and does not raise."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from app.agent.uia import snapshot
from app.agent.uia.safety import guard_action, pace


def _result(ok: bool, detail: str) -> dict[str, Any]:
    return {"ok": ok, "detail": detail}


def _log(mission_id: UUID | None, detail: str, ok: bool) -> None:
    if mission_id is None:
        return
    from app.agent.events import emit

    emit(mission_id, "ui_action", detail, {"ok": ok})


def _guard(element_id: str, mission_id: UUID | None) -> dict[str, Any] | None:
    window = snapshot.get_active_window()
    row = snapshot.element_row(element_id) or {}
    blocked = guard_action(
        str(window.get("process") or ""),
        str(row.get("name") or ""),
        str(row.get("automation_id") or ""),
        mission_id,
    )
    return blocked if isinstance(blocked, dict) else None


def focus_hwnd(hwnd: int) -> dict[str, Any]:
    try:
        import ctypes
        import win32con
        import win32gui

        if not hwnd:
            return _result(False, "Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
        try:
            win32gui.SetForegroundWindow(hwnd)
        finally:
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
        title = win32gui.GetWindowText(hwnd)
        return _result(win32gui.GetForegroundWindow() == hwnd, f"Focused {title}")
    except Exception as exc:
        return _result(False, str(exc))


def focus_window(title: str = "") -> dict[str, Any]:
    try:
        import win32gui

        if not title:
            return focus_hwnd(int(snapshot.get_active_window().get("hwnd") or 0))
        found = 0

        def visit(handle: int, _: object) -> None:
            nonlocal found
            text = win32gui.GetWindowText(handle)
            if title.lower() in text.lower() and "reborn" not in text.lower():
                found = handle

        win32gui.EnumWindows(visit, None)
        return focus_hwnd(found)
    except Exception as exc:
        return _result(False, str(exc))


def click(element_id: str, mission_id: UUID | None = None) -> dict[str, Any]:
    try:
        blocked = _guard(element_id, mission_id)
        if blocked:
            return blocked
        handle = snapshot.element_handle(element_id)
        if handle is None:
            return _result(False, f"Unknown element {element_id}")
        pace()
        try:
            handle.invoke()
            detail = f"Invoked {element_id}"
        except Exception:
            handle.click_input()
            detail = f"Clicked {element_id}"
        _log(mission_id, detail, True)
        return _result(True, detail)
    except Exception as exc:
        return _result(False, str(exc))


def type_text(element_id: str, text: str, human_delay: bool = True, mission_id: UUID | None = None) -> dict[str, Any]:
    try:
        blocked = _guard(element_id, mission_id)
        if blocked:
            return blocked
        handle = snapshot.element_handle(element_id)
        if handle is None:
            return _result(False, f"Unknown element {element_id}")
        pace()
        try:
            handle.iface_value.SetValue(text)
            detail = f"Set value on {element_id}"
        except Exception:
            handle.click_input()
            handle.type_keys("^a{BACKSPACE}", set_foreground=True)
            for char in text:
                handle.type_keys(char, with_spaces=True, pause=0.02 if human_delay else 0)
                if human_delay:
                    time.sleep(0.02)
            detail = f"Typed into {element_id}"
        _log(mission_id, detail, True)
        return _result(True, detail)
    except Exception as exc:
        return _result(False, str(exc))


def press_keys(
    keys: str,
    mission_id: UUID | None = None,
    process_name: str | None = None,
) -> dict[str, Any]:
    try:
        window = snapshot.get_active_window()
        blocked = guard_action(process_name or str(window.get("process") or ""), "", "", mission_id)
        if blocked:
            return blocked
        from pywinauto.keyboard import send_keys

        pace()
        send_keys(keys, pause=0.05)
        detail = f"Pressed {keys}"
        _log(mission_id, detail, True)
        return _result(True, detail)
    except Exception as exc:
        return _result(False, str(exc))


def select_tab(name: str, mission_id: UUID | None = None) -> dict[str, Any]:
    try:
        window = snapshot.get_active_window()
        elements = snapshot.capture_tree(window)
        match = next(
            (
                element
                for element in elements
                if element["control_type"] == "TabItem" and name.lower() in element["name"].lower()
            ),
            None,
        )
        if match is None:
            return _result(False, f"Tab not found: {name}")
        return click(match["id"], mission_id)
    except Exception as exc:
        return _result(False, str(exc))


def scroll(element_id: str, direction: str, mission_id: UUID | None = None) -> dict[str, Any]:
    try:
        handle = snapshot.element_handle(element_id)
        if handle is None:
            return _result(False, f"Unknown element {element_id}")
        pace()
        amount = 3 if direction.lower() != "up" else -3
        try:
            handle.scroll(direction, amount)
        except Exception:
            from pywinauto.keyboard import send_keys

            handle.set_focus()
            send_keys("{PGDN}" if amount > 0 else "{PGUP}")
        detail = f"Scrolled {direction}"
        _log(mission_id, detail, True)
        return _result(True, detail)
    except Exception as exc:
        return _result(False, str(exc))


def wait_for(element_name: str, timeout: float = 10) -> dict[str, Any]:
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            elements = snapshot.capture_tree()
            found = next(
                (element for element in elements if element_name.lower() in element["name"].lower()),
                None,
            )
            if found:
                return _result(True, f"Found {found['id']} {found['name']}")
            time.sleep(0.4)
        return _result(False, f"Timed out waiting for {element_name}")
    except Exception as exc:
        return _result(False, str(exc))
