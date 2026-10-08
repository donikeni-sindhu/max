import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.agent import mission_control


class MissionControlTests(unittest.TestCase):
    def test_second_run_is_rejected_until_first_releases_lock(self):
        mission_id = uuid4()
        try:
            self.assertTrue(mission_control.reserve_run(mission_id))
            self.assertFalse(mission_control.reserve_run(mission_id))
        finally:
            mission_control.release_run(mission_id)
        self.assertTrue(mission_control.reserve_run(mission_id))
        mission_control.release_run(mission_id)

    def test_cancel_blocks_the_next_action(self):
        mission_id = uuid4()
        try:
            self.assertTrue(mission_control.reserve_run(mission_id))
            self.assertTrue(mission_control.cancel(mission_id))
            allowed, reason = mission_control.authorize_action(mission_id)
        finally:
            mission_control.release_run(mission_id)
        self.assertFalse(allowed)
        self.assertEqual(reason, "Mission was cancelled")

    def test_url_is_reserved_once_per_mission_even_when_fragment_changes(self):
        mission_id = uuid4()
        try:
            self.assertTrue(mission_control.reserve_run(mission_id))
            first = mission_control.reserve_url(mission_id, "https://example.com/page#one")
            with patch("app.agent.events.emit"):
                repeated = mission_control.reserve_url(mission_id, "https://example.com/page#two")
        finally:
            mission_control.release_run(mission_id)
        self.assertTrue(first[0])
        self.assertFalse(repeated[0])
        self.assertIn("already opened", repeated[1])

    def test_action_limit_stops_the_next_action(self):
        mission_id = uuid4()
        try:
            self.assertTrue(mission_control.reserve_run(mission_id))
            with (
                patch.object(mission_control, "get_settings", return_value=SimpleNamespace(max_actions_per_mission=1)),
                patch.object(mission_control, "_report_action_limit"),
            ):
                self.assertTrue(mission_control.authorize_action(mission_id)[0])
                allowed, reason = mission_control.authorize_action(mission_id)
        finally:
            mission_control.release_run(mission_id)
        self.assertFalse(allowed)
        self.assertIn("limit reached", reason)


if __name__ == "__main__":
    unittest.main()
