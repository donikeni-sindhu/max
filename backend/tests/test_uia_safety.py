import unittest
import sys
from types import MappingProxyType, ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.agent.uia import actions, safety
from app.agent.uia.snapshot import Snapshot, _freeze, _select_frame_owner


class UiaSafetyTests(unittest.TestCase):
    def test_sensitive_action_detection_uses_whole_words(self):
        self.assertTrue(safety.needs_confirm("Submit form"))
        self.assertTrue(safety.needs_confirm("Send payment"))
        self.assertFalse(safety.needs_confirm("Display preferences"))
        self.assertFalse(safety.needs_confirm("Payment history"))
        self.assertFalse(safety.needs_confirm("Resend"))

    def test_enter_in_messaging_app_requires_send_confirmation(self):
        self.assertTrue(safety.requires_message_confirmation("WhatsApp.exe", "WhatsApp", "", "{ENTER}"))
        self.assertTrue(safety.needs_confirm("Send message"))
        self.assertFalse(safety.requires_message_confirmation("chrome.exe", "Google", "", "{ENTER}"))

    def test_pressing_enter_in_focused_whatsapp_input_forces_confirmation(self):
        """The actual keyboard action checks the focused message field and requires send approval."""

        observed = Snapshot(
            MappingProxyType({"hwnd": 123, "process": "WhatsApp.exe", "title": "WhatsApp"}),
            (MappingProxyType({"id": "e1", "name": "Message", "control_type": "Edit", "automation_id": "message", "focused": True, "hwnd": 123}),),
            MappingProxyType({"e1": object()}),
        )
        fake_win32gui = SimpleNamespace(GetForegroundWindow=lambda: 123)
        fake_pywinauto = ModuleType("pywinauto")
        fake_pywinauto.__path__ = []
        fake_keyboard = ModuleType("pywinauto.keyboard")
        fake_keyboard.send_keys = Mock()
        with (
            patch.object(actions.mission_control, "authorize_action", return_value=(True, "")),
            patch.object(actions.snapshot, "capture_tree", return_value=observed),
            patch.object(actions.snapshot, "window_context", return_value={"hwnd": 123, "process": "WhatsApp.exe", "package": ""}),
            patch.object(actions, "guard_action") as guard,
            patch.object(actions, "pace"),
            patch.object(actions, "_log"),
            patch.dict(sys.modules, {"win32gui": fake_win32gui, "pywinauto": fake_pywinauto, "pywinauto.keyboard": fake_keyboard}),
        ):
            result = actions.press_keys("{ENTER}", uuid4(), observed=observed)

        self.assertTrue(result["ok"])
        self.assertEqual(guard.call_args.args[1], "Send message")
        self.assertTrue(guard.call_args.kwargs["force_confirm"])

    def test_card_and_one_time_code_fields_are_sensitive(self):
        """Names and automation IDs for card and OTP controls are blocked from text entry too."""

        self.assertTrue(safety.is_password("Card number", "paymentCard"))
        self.assertTrue(safety.is_password("One-time code", "otpEntry"))

    def test_non_browser_interaction_approval_is_session_scoped_and_revocable(self):
        mission_id = uuid4()
        with patch.object(safety, "request_confirm", return_value=True) as confirm:
            self.assertIsNone(safety.guard_action("notepad.exe", "Text", "", mission_id))
        self.assertEqual(confirm.call_count, 1)
        self.assertIn("Notepad", safety.approved_apps())
        self.assertTrue(safety.revoke_app_approval("Notepad"))
        self.assertNotIn("Notepad", safety.approved_apps())

    def test_confirmation_timeout_rejects_the_action_and_clears_pending_state(self):
        mission_id = uuid4()
        with (
            patch("app.db.patch_world") as patch_world,
            patch("app.agent.events.emit") as emit,
            patch.object(safety, "_CONFIRM_TIMEOUT_SECONDS", 0),
            patch.object(safety.mission_control, "is_cancelled", return_value=False),
        ):
            approved = safety.request_confirm(mission_id, "Allow Submit?")

        self.assertFalse(approved)
        self.assertNotIn(str(mission_id), safety._pending)
        self.assertIn("pending_confirmation", patch_world.call_args_list[0].kwargs)
        self.assertEqual(patch_world.call_args_list[-1].kwargs["pending_confirmation"], None)
        self.assertTrue(emit.call_args_list[-1].args[3]["timeout"])

    def test_unsolicited_confirmation_cannot_be_saved_for_a_future_action(self):
        mission_id = uuid4()
        self.assertFalse(safety.resolve_confirm(mission_id, True))
        self.assertNotIn(str(mission_id), safety._answers)

    def test_snapshot_freezes_nested_lists_and_mappings(self):
        frozen = _freeze({"rect": [1, 2, 3, 4], "metadata": {"name": "Search"}})
        self.assertEqual(frozen["rect"], (1, 2, 3, 4))
        with self.assertRaises(TypeError):
            frozen["metadata"]["name"] = "Changed"

    def test_fresh_handle_rejects_a_control_from_a_different_window(self):
        observed = Snapshot(
            MappingProxyType({"hwnd": 1, "process": "chrome.exe"}),
            (MappingProxyType({"id": "e1", "name": "Search", "control_type": "Edit", "automation_id": "q", "rect": [1, 1, 2, 2]}),),
            MappingProxyType({"e1": object()}),
        )
        current = Snapshot(
            MappingProxyType({"hwnd": 2, "process": "chrome.exe"}),
            (MappingProxyType({"id": "e1", "name": "Search", "control_type": "Edit", "automation_id": "q", "rect": [1, 1, 2, 2]}),),
            MappingProxyType({"e1": object()}),
        )
        with patch.object(actions.snapshot, "capture_tree", return_value=current):
            _, handle, row = actions._fresh_handle("e1", observed, "Search")

        self.assertIsNone(handle)
        self.assertEqual(row["error"], "stale_element")

    def test_snapshot_race_resolves_only_a_matching_fresh_element(self):
        observed = Snapshot(
            MappingProxyType({"hwnd": 1}),
            (MappingProxyType({"id": "e1", "name": "Save", "control_type": "Button", "automation_id": "save"}),),
            MappingProxyType({"e1": object()}),
        )
        changed = Snapshot(
            MappingProxyType({"hwnd": 1}),
            (MappingProxyType({"id": "e1", "name": "Delete", "control_type": "Button", "automation_id": "delete"}),),
            MappingProxyType({"e1": object()}),
        )
        with patch.object(actions.snapshot, "capture_tree", return_value=changed):
            _, handle, failure = actions._fresh_handle("e1", observed, "Save")

        self.assertIsNone(handle)
        self.assertEqual(failure["error"], "stale_element")

    def test_application_frame_host_uses_real_child_process_for_policy(self):
        hwnd, pid = _select_frame_owner("ApplicationFrameHost.exe", 10, [(20, 10), (21, 42)])
        self.assertEqual((hwnd, pid), (21, 42))


if __name__ == "__main__":
    unittest.main()
