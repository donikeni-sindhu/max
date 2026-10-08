"""Chrome launch tests verify that the dedicated browser window is not assumed to exist."""

from unittest.mock import patch

from app.agent.uia import chrome


def test_chrome_launch_reports_missing_visible_window_as_failure():
    """A started process without an observable window must not carry a success-sounding detail."""

    with (
        patch.object(chrome, "chrome_path", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        patch.object(chrome.subprocess, "Popen"),
        patch.object(chrome, "_chrome_window", return_value={"hwnd": 0, "title": "", "process": "chrome.exe"}),
        patch.object(chrome.time, "sleep"),
    ):
        result = chrome.launch_chrome()

    assert result["ok"] is False
    assert result["detail"] == "Chrome did not create a visible window"


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
