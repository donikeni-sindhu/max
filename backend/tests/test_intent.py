import unittest
from unittest.mock import patch
from uuid import uuid4

from app.agent.intent import IntentResult, _fallback, parse_goal


class IntentTests(unittest.TestCase):
    def test_browser_action_with_search_routes_to_ui_command(self):
        result = _fallback("open github.com and search for fastapi")
        self.assertEqual(result.goal_type, "ui_command")

    def test_paper_word_alone_does_not_select_the_demo_paper(self):
        result = _fallback("What is written in the paper?")
        self.assertEqual(result.goal_type, "chat")
        self.assertEqual(result.target_title, "")

    def test_user_named_paper_uses_its_title(self):
        result = _fallback("I want to understand the paper 'A Different Paper'")
        self.assertEqual(result.goal_type, "paper_mission")
        self.assertEqual(result.target_title, "A Different Paper")

    def test_open_whatsapp_routes_to_app_launcher(self):
        result = _fallback("open whatsapp")
        self.assertEqual(result.goal_type, "open_app")
        self.assertEqual(result.target_app, "WhatsApp")

    def test_launch_spotify_routes_to_app_launcher(self):
        result = _fallback("launch spotify")
        self.assertEqual(result.goal_type, "open_app")
        self.assertEqual(result.target_app, "Spotify")

    def test_open_paper_on_topic_routes_to_research_with_user_topic(self):
        result = _fallback("open the paper on transformers")
        self.assertEqual(result.goal_type, "paper_mission")
        self.assertEqual(result.target_title, "transformers")

    def test_generic_goal_containing_paper_stays_chat(self):
        result = _fallback("I used paper to make a small airplane")
        self.assertEqual(result.goal_type, "chat")

    def test_paper_airplane_does_not_become_a_paper_mission(self):
        result = _fallback("Explain how a paper airplane flies")
        self.assertEqual(result.goal_type, "chat")

    def test_open_youtube_stays_a_browser_command(self):
        result = _fallback("open youtube")
        self.assertEqual(result.goal_type, "ui_command")

    def test_model_classification_is_returned_instead_of_forced_to_paper(self):
        model_result = IntentResult(goal_type="chat", response="A short answer")
        with (
            patch.dict("os.environ", {"REBORN_SKIP_UI": "0"}),
            patch("app.agent.intent.complete_json", return_value=model_result),
            patch("app.agent.intent.emit"),
        ):
            result = parse_goal(uuid4(), "paper")
        self.assertEqual(result.goal_type, "chat")


if __name__ == "__main__":
    unittest.main()
