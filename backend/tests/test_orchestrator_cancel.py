import unittest
from unittest.mock import patch
from uuid import uuid4

from app.agent import mission_control, orchestrator


class OrchestratorCancellationTests(unittest.TestCase):
    def test_cancel_during_demo_pause_raises_the_shared_cancellation_type(self):
        mission_id = uuid4()
        with (
            patch.dict("os.environ", {"REBORN_FAST": "0"}),
            patch.object(orchestrator, "get_settings", return_value=type("Settings", (), {"demo_mode": True})()),
            patch.object(mission_control, "is_cancelled", return_value=False),
            patch.object(mission_control, "wait_or_cancel", return_value=True),
        ):
            with self.assertRaises(mission_control.MissionCancelled):
                orchestrator.demo_pause(mission_id)


if __name__ == "__main__":
    unittest.main()
