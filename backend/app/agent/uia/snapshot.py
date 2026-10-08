"""Immutable, per-capture Windows UI Automation views; Windows-only imports stay inside call sites."""

from __future__ import annotations

import ctypes
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping

USEFUL_TYPES = {
    "Button", "Edit", "Tab", "TabItem", "Hyperlink", "ListItem", "MenuItem", "Document", "Text", "ComboBox",
    "CheckBox", "RadioButton", "SplitButton", "TreeItem", "DataItem", "List", "Custom", "Group", "Pane",
}

# Every tree walk and input action takes this lock because Windows UIA providers can race internally.
UIA_LOCK = threading.RLock()
_SNAPSHOT_COUNTER = 0
_last_external_window: dict[str, Any] | None = None


def _freeze(value: Any) -> Any:
    """Recursively freeze captured metadata so observer updates cannot mutate a model's source view."""

    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@contextmanager
def com_initialized() -> Iterator[None]:
    """Balance COM initialization for every thread entering UIA, while remaining importable off Windows."""

    try:
        import pythoncom
    except ImportError:
        yield
        return
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


def _next_snapshot_id() -> int:
    """Allocate monotonic IDs under a lock so simultaneous observers never share a capture number."""

    global _SNAPSHOT_COUNTER
    with UIA_LOCK:
        _SNAPSHOT_COUNTER += 1
        return _SNAPSHOT_COUNTER


@dataclass(frozen=True)
class Snapshot:
    """Pair immutable visible rows with their exact source handles and capture metadata."""

    window: Mapping[str, Any]
    elements: tuple[Mapping[str, Any], ...]
    handles: Mapping[str, Any]
    snapshot_id: int = 0
    captured_at: float = 0.0

    def element_row(self, element_id: str) -> Mapping[str, Any] | None:
        """Return the row belonging to this snapshot only, never a module-global current ID."""

        return next((row for row in self.elements if row["id"] == element_id), None)

    def element_handle(self, element_id: str) -> Any:
        """Return the wrapper paired with a row in this same immutable capture."""

        return self.handles.get(element_id)


def _excluded(title: str) -> bool:
    """Keep REBORN's own overlay out of targets so commands cannot control themselves."""

    return "reborn" in title.lower()


def _is_cloaked(hwnd: int) -> bool:
    """Ask DWM whether a visible-looking handle belongs to a hidden virtual desktop or app frame."""

    try:
        value = ctypes.c_int(0)
        status = ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(value), ctypes.sizeof(value))
        return status != 0 or value.value != 0
    except (AttributeError, OSError):
        # Older Windows or test doubles may lack DWM; IsWindowVisible remains the conservative fallback.
        return False


def is_window_visible(hwnd: int) -> bool:
    """Require a valid visible native window and reject DWM-cloaked handles before app matching."""

    try:
        import win32gui

        return bool(hwnd and win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd) and not _is_cloaked(hwnd))
    except (ImportError, OSError):
        return False


def _package_name(pid: int) -> str:
    """Resolve an MSIX package full name through Kernel32 when the owning process has package identity."""

    if not pid:
        return ""
    try:
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetPackageFullName.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
        kernel.GetPackageFullName.restype = ctypes.c_long
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_bool
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            length = ctypes.c_uint32(0)
            kernel.GetPackageFullName(handle, ctypes.byref(length), None)
            if length.value < 2:
                return ""
            buffer = ctypes.create_unicode_buffer(length.value)
            result = kernel.GetPackageFullName(handle, ctypes.byref(length), buffer)
            return buffer.value if result == 0 else ""
        finally:
            kernel.CloseHandle(handle)
    except (AttributeError, OSError, TypeError):
        return ""


def _process(pid: int) -> str:
    """Resolve a PID defensively so a process exiting during capture does not discard the snapshot."""

    try:
        import psutil

        return psutil.Process(pid).name()
    except (ImportError, OSError, RuntimeError):
        return ""


def _select_frame_owner(frame_process: str, frame_pid: int, child_owners: list[tuple[int, int]]) -> tuple[int, int]:
    """Choose a non-frame child HWND/PID for a hosted Store app, or retain the original owner if absent."""

    if frame_process.casefold() != "applicationframehost.exe":
        return 0, frame_pid
    matching = [(hwnd, pid) for hwnd, pid in child_owners if pid and pid != frame_pid]
    return matching[-1] if matching else (0, frame_pid)


def window_context(hwnd: int) -> dict[str, Any]:
    """Describe the process behind a window, including the child process hosted by ApplicationFrameHost."""

    import win32gui
    import win32process

    title = win32gui.GetWindowText(hwnd) if hwnd else ""
    _, pid = win32process.GetWindowThreadProcessId(hwnd) if hwnd else (0, 0)
    process = _process(pid)
    owner_hwnd = hwnd
    if process.casefold() == "applicationframehost.exe":
        child_owners: list[tuple[int, int]] = []

        def visit(child: int, _: object) -> None:
            _, child_pid = win32process.GetWindowThreadProcessId(child)
            if child_pid and child_pid != pid:
                child_owners.append((child, child_pid))

        win32gui.EnumChildWindows(hwnd, visit, None)
        owner_hwnd, child_pid = _select_frame_owner(process, pid, child_owners)
        if owner_hwnd:
            # The final visible non-frame child usually owns the hosted app content and its package identity.
            pid = child_pid
            process = _process(pid)
    try:
        rect = list(win32gui.GetWindowRect(hwnd)) if hwnd else [0, 0, 0, 0]
    except OSError:
        rect = [0, 0, 0, 0]
    return {
        "title": title,
        "process": process,
        "pid": pid,
        "hwnd": hwnd,
        "owner_hwnd": owner_hwnd,
        "package": _package_name(pid),
        "rect": rect,
    }


def get_active_window(target_hwnd: int | None = None) -> dict[str, Any]:
    """Use the foreground or run-recorded window; never pick an arbitrary window when REBORN has focus."""

    global _last_external_window
    try:
        import win32gui
    except ImportError as exc:
        return {"title": "", "process": "", "pid": 0, "hwnd": 0, "rect": [0, 0, 0, 0], "detail": str(exc)}
    with UIA_LOCK:
        foreground = int(win32gui.GetForegroundWindow() or 0)
        candidate = target_hwnd if target_hwnd and is_window_visible(target_hwnd) else foreground
        if candidate and is_window_visible(candidate):
            details = window_context(candidate)
            if not _excluded(str(details.get("title") or "")):
                _last_external_window = details
                return details
        # A previously observed target is safe to reuse when REBORN's widget takes focus mid-run.
        if _last_external_window and is_window_visible(int(_last_external_window.get("hwnd") or 0)):
            return dict(_last_external_window)
        return {"title": "", "process": "", "pid": 0, "hwnd": 0, "rect": [0, 0, 0, 0]}


def initialize_dpi_awareness() -> None:
    """Set Windows process DPI mode before UIA rectangles are compared with physical click coordinates."""

    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            # A host may already have locked DPI mode; keeping startup alive is safer than a late override.
            return


def _offscreen(element: Any) -> bool:
    """Exclude controls that UIA reports outside the visible viewport."""

    try:
        return bool(element.iface_element.CurrentIsOffscreen)
    except Exception:
        return False


def _is_focusable_or_invokable(element: Any) -> bool:
    """Retain named-only container types when UIA reports an actual focus or invoke capability."""

    try:
        return bool(element.element_info.is_keyboard_focusable or element.iface_invoke)
    except Exception:
        try:
            return bool(element.element_info.is_keyboard_focusable)
        except Exception:
            return False


def _record(element: Any, element_id: str, parent_id: str | None) -> Mapping[str, Any] | None:
    """Create a compact row while preserving enough identity to re-resolve a control before input."""

    info = element.element_info
    name = (info.name or "").strip()
    control_type = info.control_type or ""
    automation_id = info.automation_id or ""
    if control_type not in USEFUL_TYPES or _offscreen(element):
        return None
    if not name and control_type not in {"Edit", "Document"} and not (control_type == "Button" and automation_id):
        if control_type not in {"Pane", "Group", "List", "Custom"} or not _is_focusable_or_invokable(element):
            return None
    if control_type == "Text" and len(name) < 2:
        return None
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
        pass
    focused = False
    try:
        focused = bool(element.has_keyboard_focus())
    except Exception:
        pass
    try:
        hwnd = int(info.handle or 0)
    except (AttributeError, TypeError, ValueError):
        hwnd = 0
    try:
        password = bool(element.iface_value.CurrentIsPassword)
    except Exception:
        password = False
    row = {
        "id": element_id,
        "name": name,
        "control_type": control_type,
        "automation_id": automation_id,
        "class_name": info.class_name or "",
        "enabled": bool(info.enabled),
        "focused": focused,
        "password": password,
        "offscreen": False,
        "rect": tuple(rect),
        "value": str(value)[:300],
        "hwnd": hwnd,
        "parent_id": parent_id,
    }
    return MappingProxyType(row)


def _empty_snapshot(window: dict[str, Any]) -> Snapshot:
    """Give even an unavailable-window capture a unique ID and timestamp for race diagnostics."""

    return Snapshot(_freeze(window), (), MappingProxyType({}), _next_snapshot_id(), time.monotonic())


def capture_tree(
    window: dict[str, Any] | None = None,
    max_depth: int = 6,
    max_elements: int = 150,
) -> Snapshot:
    """Capture a breadth-first, depth-budgeted tree so title-bar controls cannot consume the whole result."""

    with com_initialized(), UIA_LOCK:
        target = window or get_active_window()
        hwnd = int(target.get("hwnd") or 0)
        if not hwnd or _excluded(str(target.get("title") or "")):
            return _empty_snapshot(dict(target))
        try:
            from pywinauto import Desktop

            root = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
        except (ImportError, OSError, RuntimeError):
            return _empty_snapshot(dict(target))
        rows: list[Mapping[str, Any]] = []
        handles: dict[str, Any] = {}
        row_ids: dict[int, str] = {}
        # Budgets reserve places for deeper controls such as search boxes and message fields.
        depth_budget = [12, 28, 32, 32, 24, 14, 8]
        queue: deque[tuple[Any, int, int | None]] = deque([(root, 0, None)])
        seen_at_depth = [0] * (max_depth + 1)
        queued_at_depth = [0] * (max_depth + 1)
        queued_at_depth[0] = 1
        while queue and len(rows) < max_elements:
            node, depth, parent_key = queue.popleft()
            if depth > max_depth or seen_at_depth[depth] >= depth_budget[min(depth, len(depth_budget) - 1)]:
                continue
            seen_at_depth[depth] += 1
            try:
                element_id = f"e{len(rows) + 1}"
                parent_id = row_ids.get(parent_key) if parent_key is not None else None
                row = _record(node, element_id, parent_id)
                if row is not None:
                    rows.append(row)
                    handles[element_id] = node
                    try:
                        row_ids[int(node.element_info.handle)] = element_id
                    except (AttributeError, TypeError, ValueError):
                        pass
            except Exception:
                row = None
            if depth >= max_depth:
                continue
            # Enumerate one direct-child level at a time; descendants() materializes huge Chromium trees.
            try:
                children = node.children()
            except Exception:
                children = ()
            for child in children:
                # Cap queued nodes too, because a single browser provider can expose thousands of siblings.
                next_depth = depth + 1
                if queued_at_depth[next_depth] >= depth_budget[min(next_depth, len(depth_budget) - 1)]:
                    break
                queue.append((child, depth + 1, int(node.element_info.handle) if getattr(node.element_info, "handle", None) else None))
                queued_at_depth[next_depth] += 1
        return Snapshot(_freeze(dict(target)), tuple(rows), MappingProxyType(handles), _next_snapshot_id(), time.monotonic())


def compact_for_llm(elements: Snapshot | Iterable[Mapping[str, Any]]) -> str:
    """Render visible IDs and stable labels for the model without leaking element handles or process data."""

    rows = elements.elements if isinstance(elements, Snapshot) else elements
    lines: list[str] = []
    used = 0
    for element in rows:
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
