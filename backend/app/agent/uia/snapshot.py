"""Windows UI Automation snapshots. REBORN's own window is ignored."""

from __future__ import annotations

from typing import Any

USEFUL_TYPES = {
    "Button",
    "Edit",
    "Tab",
    "TabItem",
    "Hyperlink",
    "ListItem",
    "MenuItem",
    "Document",
    "Text",
    "ComboBox",
}

HANDLES: dict[str, Any] = {}
ELEMENTS: dict[str, dict[str, Any]] = {}


def _excluded(title: str) -> bool:
    return "reborn" in title.lower()


def get_active_window() -> dict[str, Any]:
    try:
        import psutil
        import win32gui
        import win32process
    except Exception as exc:
        return {"title": "", "process": "", "pid": 0, "hwnd": 0, "rect": [0, 0, 0, 0], "detail": str(exc)}

    hwnd = win32gui.GetForegroundWindow()
    chosen = hwnd
    title = win32gui.GetWindowText(hwnd) if hwnd else ""
    if _excluded(title):
        found: list[int] = []

        def visit(handle: int, _: object) -> None:
            if not win32gui.IsWindowVisible(handle):
                return
            text = win32gui.GetWindowText(handle)
            if text and not _excluded(text):
                found.append(handle)

        win32gui.EnumWindows(visit, None)
        chosen = found[0] if found else 0
        title = win32gui.GetWindowText(chosen) if chosen else ""

    pid = 0
    process = ""
    rect = [0, 0, 0, 0]
    if chosen:
        _, pid = win32process.GetWindowThreadProcessId(chosen)
        try:
            process = psutil.Process(pid).name()
        except Exception:
            process = ""
        try:
            rect = list(win32gui.GetWindowRect(chosen))
        except Exception:
            rect = [0, 0, 0, 0]
    return {"title": title, "process": process, "pid": pid, "hwnd": chosen, "rect": rect}


def _offscreen(element: Any) -> bool:
    try:
        return bool(element.iface_element.CurrentIsOffscreen)
    except Exception:
        return False


def _record(element: Any, parent_id: str | None) -> dict[str, Any] | None:
    info = element.element_info
    name = (info.name or "").strip()
    control_type = info.control_type or ""
    if control_type not in USEFUL_TYPES:
        return None
    if _offscreen(element):
        return None
    if not name and control_type not in {"Edit", "Document"}:
        return None
    if control_type == "Text" and len(name) < 2:
        return None
    element_id = f"e{len(ELEMENTS) + 1}"
    rect = [0, 0, 0, 0]
    try:
        box = element.rectangle()
        rect = [box.left, box.top, box.right, box.bottom]
    except Exception:
        pass
    value = ""
    try:
        value = element.iface_value.CurrentValue or ""
    except Exception:
        value = ""
    focused = False
    try:
        focused = bool(element.has_keyboard_focus())
    except Exception:
        focused = False
    row = {
        "id": element_id,
        "name": name,
        "control_type": control_type,
        "automation_id": info.automation_id or "",
        "class_name": info.class_name or "",
        "enabled": bool(info.enabled),
        "focused": focused,
        "offscreen": False,
        "rect": rect,
        "value": value[:300],
        "parent_id": parent_id,
    }
    ELEMENTS[element_id] = row
    HANDLES[element_id] = element
    return row


def capture_tree(
    window: dict[str, Any] | None = None,
    max_depth: int = 6,
    max_elements: int = 150,
) -> list[dict[str, Any]]:
    ELEMENTS.clear()
    HANDLES.clear()
    target = window or get_active_window()
    hwnd = int(target.get("hwnd") or 0)
    if not hwnd or _excluded(str(target.get("title") or "")):
        return []
    try:
        from pywinauto import Desktop

        root = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    except Exception:
        return []

    nodes: list[Any] = [root]
    try:
        nodes.extend(root.descendants(depth=max_depth))
    except Exception:
        pass
    for node in nodes:
        if len(ELEMENTS) >= max_elements:
            break
        try:
            _record(node, None)
        except Exception:
            continue
    return list(ELEMENTS.values())


def compact_for_llm(elements: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    used = 0
    for element in elements:
        flags: list[str] = []
        if element.get("enabled"):
            flags.append("enabled")
        if element.get("focused"):
            flags.append("focused")
        name = str(element.get("name") or "").replace("\n", " ")[:80]
        line = f"{element['id']} {element['control_type']} \"{name}\" {' '.join(flags)}".rstrip()
        if used + len(line) > 11000:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def element_row(element_id: str) -> dict[str, Any] | None:
    return ELEMENTS.get(element_id)


def element_handle(element_id: str) -> Any:
    return HANDLES.get(element_id)
