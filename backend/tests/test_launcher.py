"""Pure strategy-ladder tests; Windows APIs are replaced so pytest also runs on non-Windows hosts."""

from uuid import uuid4
from unittest.mock import patch

from app.agent import launcher


def test_start_apps_fuzzy_match_handles_alias_prefix_and_rejects_weak_matches():
    """Match common names and short prefixes while refusing unrelated Start-app entries."""

    entries = [
        {"Name": "WhatsApp", "AppID": "WhatsApp.App"},
        {"Name": "Calculator", "AppID": "Microsoft.WindowsCalculator"},
        {"Name": "Photos", "AppID": "Microsoft.Photos"},
    ]
    assert launcher.match_start_app("whatsapp", entries)["Name"] == "WhatsApp"
    assert launcher.match_start_app("calc", entries)["Name"] == "Calculator"
    assert launcher.match_start_app("unrelated editor", entries) is None


def test_launch_ladder_skips_unverified_route_then_stops_at_verified_route():
    """An OS request without window proof must fall through before a later verified route succeeds."""

    tried = []
    routes = {
        name: (lambda target, name=name: (tried.append(name) or {"ok": True, "detail": f"started by {name}", "evidence": {}}))
        for name in launcher._STRATEGY_NAMES
    }
    verification = iter([None, {"title": "WhatsApp", "process": "WhatsApp.exe", "hwnd": 42}])
    with patch("app.agent.launcher.emit"):
        result = launcher.launch_app(
            "WhatsApp",
            uuid4(),
            strategy_overrides=routes,
            verifier=lambda target, web: next(verification),
        )

    assert tried == ["focus_running", "ui_element"]
    assert result["ok"] is True
    assert result["strategy"] == "ui_element"
    assert result["evidence"]["hwnd"] == 42
    assert "via ui_element" in result["detail"]
    assert "WhatsApp" in result["detail"]
    assert result["attempts"][0]["error"] == "launch_unverified"


def test_launch_ladder_stops_after_first_verified_strategy():
    """A verified foreground window is sufficient evidence and prevents later routes from launching duplicates."""

    tried = []
    routes = {
        name: (lambda target, name=name: (tried.append(name) or {"ok": True, "detail": "started", "evidence": {}}))
        for name in launcher._STRATEGY_NAMES
    }
    evidence = {"title": "Spotify", "process": "Spotify.exe", "hwnd": 84}
    with patch("app.agent.launcher.emit"):
        result = launcher.launch_app("Spotify", strategy_overrides=routes, verifier=lambda target, web: evidence)

    assert result["ok"] is True
    assert tried == ["focus_running"]
    assert len(result["attempts"]) == 1
