"""Chrome launch tests verify that the dedicated browser window is not assumed to exist."""

import sys
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.uia import chrome


def test_chrome_launch_reports_missing_visible_window_as_failure():
    """A started process without an observable window must not carry a success-sounding detail."""

    with (
        patch.object(chrome, "chrome_path", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        patch.object(chrome.subprocess, "Popen") as popen,
        patch.object(chrome, "_chrome_window", return_value={"hwnd": 0, "title": "", "process": "chrome.exe"}),
        patch.object(chrome.time, "sleep"),
    ):
        result = chrome.launch_chrome()

    assert result["ok"] is False
    assert result["detail"] == "Chrome did not create a visible window"
    assert "--new-window" in popen.call_args.args[0]


def test_chrome_launch_returns_window_evidence_after_visibility_is_verified():
    """Successful Chrome startup includes the title, executable identity, and native window handle."""

    visible = {"hwnd": 42, "title": "New Tab - Google Chrome", "process": "chrome.exe"}
    with (
        patch.object(chrome, "chrome_path", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        patch.object(chrome.subprocess, "Popen"),
        patch.object(chrome, "_chrome_window", return_value=visible),
        patch.object(chrome.time, "sleep"),
    ):
        result = chrome.launch_chrome()

    assert result["ok"] is True
    assert result["evidence"] == {"title": visible["title"], "process": visible["process"], "hwnd": 42}


def test_chrome_window_falls_back_to_a_visible_regular_profile():
    """An already-open user Chrome window is usable when REBORN's dedicated profile is absent."""

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            return "chrome.exe"

        def cmdline(self):
            return ["chrome.exe", "--user-data-dir=C:\\Users\\test\\Default"]

        def parents(self):
            return []

    win32gui = SimpleNamespace(
        EnumWindows=lambda callback, _: (callback(11, None), callback(22, None)),
        GetWindowText=lambda hwnd: f"Chrome {hwnd}",
    )
    win32process = SimpleNamespace(GetWindowThreadProcessId=lambda hwnd: (0, hwnd))
    with (
        patch.dict(sys.modules, {
            "psutil": SimpleNamespace(Process=FakeProcess),
            "win32gui": win32gui,
            "win32process": win32process,
        }),
        patch.object(chrome.snapshot, "is_window_visible", return_value=True),
    ):
        assert chrome._chrome_hwnd() == 11


def test_chrome_window_prefers_the_dedicated_profile_over_regular_chrome():
    """When both windows exist, retain REBORN's isolated profile as the preferred target."""

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            return "chrome.exe"

        def cmdline(self):
            profile = "chrome-profile" if self.pid == 22 else "Default"
            return ["chrome.exe", f"--user-data-dir={profile}"]

        def parents(self):
            return []

    win32gui = SimpleNamespace(
        EnumWindows=lambda callback, _: (callback(11, None), callback(22, None)),
        GetWindowText=lambda hwnd: f"Chrome {hwnd}",
    )
    win32process = SimpleNamespace(GetWindowThreadProcessId=lambda hwnd: (0, hwnd))
    with (
        patch.dict(sys.modules, {
            "psutil": SimpleNamespace(Process=FakeProcess),
            "win32gui": win32gui,
            "win32process": win32process,
        }),
        patch.object(chrome.snapshot, "is_window_visible", return_value=True),
    ):
        assert chrome._chrome_hwnd() == 22
