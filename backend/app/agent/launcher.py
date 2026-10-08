"""Launch named Windows apps through ordered routes and report only verified foreground windows."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from app.agent import apps, mission_control
from app.agent.events import emit
from app.agent.uia import snapshot
from app.config import get_settings

_logger = logging.getLogger(__name__)
_START_APPS_THRESHOLD = 0.68
_STRATEGY_NAMES = (
    "focus_running",
    "ui_element",
    "start_apps",
    "protocol",
    "start_menu_shortcut",
    "app_paths",
    "web_fallback",
)


def _tokens(value: str) -> tuple[str, ...]:
    """Normalize a candidate to words so fuzzy matching works without adding a platform dependency."""

    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def start_app_score(query: str, candidate: str) -> float:
    """Score app labels by token coverage while allowing short prefixes such as `calc` for `Calculator`."""

    wanted = _tokens(query)
    offered = _tokens(candidate)
    if not wanted or not offered:
        return 0.0
    if wanted == offered:
        return 1.0
    matches = sum(
        any(token == other or (len(token) >= 3 and (token.startswith(other) or other.startswith(token))) for other in offered)
        for token in wanted
    )
    precision = matches / len(wanted)
    recall = matches / len(offered)
    # Favor coverage of every user word while still distinguishing generic partial matches.
    return 0.7 * precision + 0.3 * recall


def match_start_app(query: str, entries: list[dict[str, str]], threshold: float = _START_APPS_THRESHOLD) -> dict[str, str] | None:
    """Choose the best Start-app result only when its token score clears the conservative threshold."""

    ranked = sorted(entries, key=lambda row: start_app_score(query, row.get("Name", "")), reverse=True)
    if not ranked or start_app_score(query, ranked[0].get("Name", "")) < threshold:
        return None
    if len(ranked) > 1 and start_app_score(query, ranked[0].get("Name", "")) == start_app_score(query, ranked[1].get("Name", "")):
        return None
    return ranked[0]


def _result(strategy: str, ok: bool, detail: str, evidence: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    """Keep every strategy result structurally consistent so the ladder can log and explain failures."""

    return {"ok": ok, "strategy": strategy, "detail": detail, "evidence": evidence or {}, **extra}


def _windows() -> list[dict[str, Any]]:
    """Enumerate only visible, uncloaked top-level windows and resolve Store app frame owners."""

    import win32gui

    found: list[dict[str, Any]] = []

    def visit(hwnd: int, _: object) -> None:
        if snapshot.is_window_visible(hwnd):
            try:
                found.append(snapshot.window_context(hwnd))
            except (OSError, RuntimeError, ValueError) as exc:
                # One inaccessible top-level window must not prevent matching a different app window.
                _logger.debug("Skipping window %s during launch discovery: %s", hwnd, exc)

    win32gui.EnumWindows(visit, None)
    return found


def _matches(target: str, window: dict[str, Any], spec: apps.AppSpec | None) -> bool:
    """Match a target against title, resolved process, or package without relying on the foreground app."""

    title = str(window.get("title") or "")
    process = str(window.get("process") or "")
    package = str(window.get("package") or "")
    if spec is not None:
        normalized_process = process.casefold()
        normalized_package = package.casefold()
        if any(item.casefold() == normalized_process for item in spec.process_names):
            return True
        if any(item.casefold() in normalized_package for item in spec.package_names):
            return True
        if any(item.casefold() in title.casefold() for item in spec.window_titles):
            return True
        if spec.name.casefold() in title.casefold():
            return True
    wanted = " ".join(_tokens(target))
    if not wanted:
        return False
    return wanted in " ".join(_tokens(title)) or wanted in " ".join(_tokens(process)) or wanted in " ".join(_tokens(package))


def _focus(hwnd: int) -> bool:
    """Restore only minimized windows, then request foreground activation without changing maximized state."""

    import ctypes
    import win32con
    import win32gui

    if not hwnd or not snapshot.is_window_visible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    # Toggling Alt permits SetForegroundWindow for a user-requested launch from the widget process.
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    finally:
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    return win32gui.GetForegroundWindow() == hwnd


def _verified_window(target: str, web_fallback: bool = False) -> dict[str, Any] | None:
    """Return proof only after a matching visible window is also the actual foreground window."""

    import win32gui

    spec = apps.lookup(target)
    for window in _windows():
        if not _matches(target, window, spec):
            continue
        hwnd = int(window.get("hwnd") or 0)
        if _focus(hwnd) and win32gui.GetForegroundWindow() == hwnd:
            evidence = {key: window.get(key) for key in ("title", "process", "package", "hwnd")}
            evidence["web_version"] = web_fallback
            return evidence
    return None


def _wait_for_window(target: str, web_fallback: bool = False) -> dict[str, Any] | None:
    """Poll for app evidence up to the configured timeout instead of treating process creation as success."""

    deadline = time.monotonic() + max(0.1, get_settings().launch_verify_timeout)
    while time.monotonic() < deadline:
        try:
            evidence = _verified_window(target, web_fallback)
        except Exception as exc:
            # Provider errors differ across Win32 and pywinauto versions; one failed verifier must not hide later routes.
            _logger.info("Could not inspect app windows while verifying %s: %s", target, exc)
            return None
        if evidence:
            return evidence
        time.sleep(0.25)
    return None


def _focus_running(target: str) -> dict[str, Any]:
    """Find an existing app window by metadata and focus it before the shared verifier checks it."""

    spec = apps.lookup(target)
    for window in _windows():
        if _matches(target, window, spec) and _focus(int(window.get("hwnd") or 0)):
            return _result("focus_running", True, "Focused an existing app window", window)
    return _result("focus_running", False, "No matching visible app window was found")


def _ui_element(target: str, mission_id: UUID | None) -> dict[str, Any]:
    """Delegate taskbar, desktop, or Start-result clicks to the executor's UIA-safe launch helper."""

    from app.agent.uia.executor import launch_via_ui_element

    detail = launch_via_ui_element(target, mission_id)
    return _result("ui_element", bool(detail.get("ok")), str(detail.get("detail") or "No matching launch element was found"), detail.get("evidence"))


def _start_apps(target: str) -> dict[str, Any]:
    """Use Windows' installed-app catalogue for both Win32 and packaged Start-menu registrations."""

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json"],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        decoded = json.loads(completed.stdout or "[]")
        entries = decoded if isinstance(decoded, list) else [decoded]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return _result("start_apps", False, f"Could not read Get-StartApps: {exc}")
    match = match_start_app(target, [entry for entry in entries if isinstance(entry, dict)])
    if not match or not match.get("AppID"):
        return _result("start_apps", False, "No sufficiently close Get-StartApps match was found")
    app_id = str(match["AppID"])
    try:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
    except OSError as exc:
        return _result("start_apps", False, f"Could not launch {match.get('Name')}: {exc}", {"name": match.get("Name"), "app_id": app_id})
    return _result("start_apps", True, f"Requested {match.get('Name')} through AppsFolder", {"name": match.get("Name"), "app_id": app_id})


def _protocol(target: str) -> dict[str, Any]:
    """Launch an app scheme only after the Windows registry proves that the scheme is registered."""

    spec = apps.lookup(target)
    if not spec or not spec.protocol:
        return _result("protocol", False, "The app registry has no protocol hint for this name")
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, spec.protocol) as key:
            try:
                winreg.OpenKey(key, r"shell\open\command").Close()
            except OSError:
                # Packaged protocols may declare URL Protocol directly without a classic open command.
                winreg.QueryValueEx(key, "URL Protocol")
        os.startfile(f"{spec.protocol}:")
    except (ImportError, OSError) as exc:
        return _result("protocol", False, f"Protocol {spec.protocol}: was not launchable: {exc}")
    return _result("protocol", True, f"Requested {target} through its registered protocol", {"scheme": spec.protocol})


def _shortcut_roots() -> tuple[Path, ...]:
    """Resolve the two standard Start-menu shortcut roots without assuming either exists."""

    roots = (
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    )
    return tuple(root for root in roots if str(root) and root.exists())


def _start_menu_shortcut(target: str) -> dict[str, Any]:
    """Find a named .lnk in the standard Start-menu trees and ask Windows to open that shortcut."""

    spec = apps.lookup(target)
    wanted = spec.name if spec else target
    matches: list[tuple[float, Path]] = []
    for root in _shortcut_roots():
        for shortcut in root.rglob("*.lnk"):
            score = start_app_score(wanted, shortcut.stem)
            if score >= _START_APPS_THRESHOLD:
                matches.append((score, shortcut))
    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches or (len(matches) > 1 and matches[0][0] == matches[1][0]):
        return _result("start_menu_shortcut", False, "No unambiguous matching Start-menu shortcut was found")
    shortcut = matches[0][1]
    try:
        os.startfile(str(shortcut))
    except OSError as exc:
        return _result("start_menu_shortcut", False, f"Could not open shortcut {shortcut.name}: {exc}")
    return _result("start_menu_shortcut", True, f"Opened Start-menu shortcut {shortcut.stem}", {"shortcut": str(shortcut)})


def _app_paths(target: str) -> dict[str, Any]:
    """Resolve classic executable paths from App Paths and PATH without requiring a registry entry."""

    candidates = [target]
    spec = apps.lookup(target)
    if spec:
        candidates.extend(spec.process_names)
    for candidate in tuple(candidates):
        if not candidate.lower().endswith(".exe"):
            candidates.append(f"{candidate}.exe")
    try:
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for candidate in candidates:
                key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{candidate}"
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        executable = winreg.QueryValue(key, None)
                    if executable and Path(executable.strip('"')).exists():
                        subprocess.Popen([executable.strip('"')])
                        return _result("app_paths", True, f"Launched {candidate} from App Paths", {"executable": executable})
                except OSError:
                    continue
    except ImportError:
        pass
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            try:
                subprocess.Popen([executable])
                return _result("app_paths", True, f"Launched {candidate} from PATH", {"executable": executable})
            except OSError as exc:
                return _result("app_paths", False, f"Could not launch {candidate}: {exc}")
    return _result("app_paths", False, "No App Paths or PATH executable matched the app")


def _web_fallback(target: str, mission_id: UUID | None) -> dict[str, Any]:
    """Open only a registry-listed web companion through REBORN's dedicated Chrome profile."""

    spec = apps.lookup(target)
    if not spec or not spec.web_url:
        return _result("web_fallback", False, "No web version is registered for this app")
    from app.agent.uia import chrome

    opened = chrome.open_url(spec.web_url, mission_id)
    return _result(
        "web_fallback",
        bool(opened.get("ok")),
        f"Opened the web version of {spec.name}" if opened.get("ok") else str(opened.get("detail") or "Web version could not be opened"),
        {"url": spec.web_url, "tab": opened.get("tab"), "web_version": True},
    )


def _strategy_functions(mission_id: UUID | None) -> dict[str, Callable[[str], dict[str, Any]]]:
    """Bind mission context to strategies while keeping each route individually replaceable in tests."""

    return {
        "focus_running": lambda name: _focus_running(name),
        "ui_element": lambda name: _ui_element(name, mission_id),
        "start_apps": _start_apps,
        "protocol": _protocol,
        "start_menu_shortcut": _start_menu_shortcut,
        "app_paths": _app_paths,
        "web_fallback": lambda name: _web_fallback(name, mission_id),
    }


def launch_app(
    target: str,
    mission_id: UUID | None = None,
    strategy_overrides: dict[str, Callable[[str], dict[str, Any]]] | None = None,
    verifier: Callable[[str, bool], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Try routes in order, publish every outcome, and stop only after visible foreground evidence exists."""

    # Canonicalize registry aliases so `calc` and `Calculator` share the same per-mission duplicate guard.
    spec = apps.lookup(target)
    target = spec.name if spec else target.strip()
    if mission_id is not None:
        reserved, detail = mission_control.reserve_app(mission_id, target)
        if not reserved:
            failed = _result("already_attempted", False, detail, error="duplicate_app")
            _publish_attempt(mission_id, failed)
            return {**failed, "attempts": [failed]}
    routes = _strategy_functions(mission_id)
    if strategy_overrides:
        routes.update(strategy_overrides)
    verify = verifier or (lambda name, web: _wait_for_window(name, web))
    attempts: list[dict[str, Any]] = []
    for strategy in _STRATEGY_NAMES:
        _publish_strategy_start(mission_id, target, strategy)
        if mission_id is not None:
            authorized, detail = mission_control.authorize_action(mission_id)
            if not authorized:
                attempt = _result(strategy, False, detail, error="action_limit")
                attempts.append(attempt)
                _publish_attempt(mission_id, attempt)
                break
        try:
            attempt = routes[strategy](target)
        except Exception as exc:
            # A strategy is an isolated route; recording its exception lets the rest of the ladder continue safely.
            _logger.exception("App launch strategy %s failed for %s", strategy, target)
            attempt = _result(strategy, False, f"{type(exc).__name__}: {exc}")
        attempt = {**_result(strategy, False, "Strategy failed"), **attempt, "strategy": strategy}
        verified = None
        if attempt.get("ok"):
            web = strategy == "web_fallback"
            try:
                verified = verify(target, web)
            except Exception as exc:
                # Verification libraries raise different exception classes on different Windows builds.
                _logger.info("Could not verify route %s for %s: %s", strategy, target, exc)
                attempt["detail"] = f"Window verification failed: {exc}"
            if verified:
                # Include the observed window identity in visible text so success is auditable in the widget.
                title = str(verified.get("title") or "untitled window")
                process = str(verified.get("process") or "unknown process")
                hwnd = verified.get("hwnd")
                attempt["evidence"] = verified
                attempt["detail"] = (
                    f"{attempt['detail']} via {strategy}; verified window '{title}' "
                    f"({process}, hwnd {hwnd})"
                )
                attempts.append(attempt)
                _publish_attempt(mission_id, attempt)
                if mission_id is not None:
                    emit(mission_id, "app_opened", attempt["detail"], {"target": target, "strategy": strategy, "evidence": verified})
                return {**attempt, "attempts": attempts}
            attempt["ok"] = False
            attempt["error"] = "launch_unverified"
            attempt["detail"] = f"launch_unverified: {attempt.get('detail', 'route returned without a visible focused window')}"
        attempts.append(attempt)
        _publish_attempt(mission_id, attempt)
    details = "; ".join(f"{item['strategy']}: {item['detail']}" for item in attempts)
    final_error = next((str(item.get("error")) for item in reversed(attempts) if item.get("error") == "action_limit"), "")
    if not final_error:
        final_error = "launch_unverified" if any(item.get("error") == "launch_unverified" for item in attempts) else "launch_failed"
    return _result("exhausted", False, f"Could not open {target}. Tried: {details}", {"attempts": attempts}, error=final_error)


def _publish_attempt(mission_id: UUID | None, attempt: dict[str, Any]) -> None:
    """Stream a strategy outcome so the widget can show what REBORN tried before the final result."""

    if mission_id is not None:
        state = "verified" if attempt.get("ok") else "failed"
        emit(
            mission_id,
            "launch_attempt",
            f"{attempt['strategy']} {state}: {attempt['detail']}",
            {"strategy": attempt["strategy"], "ok": attempt.get("ok", False), "detail": attempt["detail"], "evidence": attempt.get("evidence", {})},
        )


def _publish_strategy_start(mission_id: UUID | None, target: str, strategy: str) -> None:
    """Show the next route before executing it so the widget can tell users what REBORN is trying."""

    if mission_id is not None:
        emit(mission_id, "launch_attempt", f"Trying {strategy} to open {target}", {"strategy": strategy, "phase": "trying"})
