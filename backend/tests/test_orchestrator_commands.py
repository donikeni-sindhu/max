from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agent import orchestrator


def test_explicit_youtube_video_request_opens_search_without_ui_model():
    """A compound site command must never be handed to the app launcher as an app name."""

    mission_id = uuid4()
    url = "https://www.youtube.com/results?search_query=3blue1brown"
    with (
        patch.object(orchestrator.db, "update_mission"),
        patch.object(orchestrator.chrome, "open_url", return_value={"ok": True}) as open_url,
        patch.object(orchestrator.intent, "parse_goal") as parse_goal,
        patch.object(orchestrator.executor, "run_command") as run_command,
        patch.object(orchestrator, "emit"),
    ):
        orchestrator._run_once(mission_id, "open youtube and open 3blue1brown video")

    open_url.assert_called_once_with(url, mission_id)
    parse_goal.assert_not_called()
    run_command.assert_not_called()


def test_explicit_youtube_request_reports_browser_open_failure():
    """A failed browser launch remains a concrete mission error instead of a fake success."""

    mission_id = uuid4()
    with (
        patch.object(orchestrator.db, "update_mission"),
        patch.object(orchestrator.chrome, "open_url", return_value={"ok": False, "detail": "No browser window"}),
    ):
        with pytest.raises(RuntimeError, match="No browser window"):
            orchestrator._run_once(mission_id, "open youtube and open 3blue1brown video")
