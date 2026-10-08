import unittest
from unittest.mock import patch

from app.agent.commands import parse_open_command
from app.routes.commands import CommandRequest, execute_command


class ParseOpenCommandTests(unittest.TestCase):
    def test_opens_youtube_by_name(self):
        # A bare well-known name should resolve to the canonical homepage users expect.
        self.assertEqual(parse_open_command("open youtube"), "https://www.youtube.com/")

    def test_accepts_polite_site_command(self):
        self.assertEqual(parse_open_command("Please go to youtube.com."), "https://www.youtube.com/")

    def test_accepts_an_explicit_https_url(self):
        self.assertEqual(
            parse_open_command("open https://example.com/watch?v=1"),
            "https://example.com/watch?v=1",
        )

    def test_adds_https_to_a_domain(self):
        self.assertEqual(parse_open_command("visit example.com/news"), "https://example.com/news")

    def test_does_not_treat_learning_goals_as_browser_commands(self):
        self.assertIsNone(parse_open_command("I want to learn about YouTube"))

    def test_rejects_non_web_schemes(self):
        self.assertIsNone(parse_open_command("open javascript:alert(1)"))

    def test_command_endpoint_opens_youtube_directly(self):
        with patch("app.routes.commands.chrome.open_url", return_value={"ok": True}) as open_url:
            result = execute_command(CommandRequest(command="open youtube"))

        self.assertEqual(result["url"], "https://www.youtube.com/")
        self.assertTrue(result["handled"])
        open_url.assert_called_once_with("https://www.youtube.com/")

    def test_command_endpoint_leaves_learning_goals_unhandled(self):
        with patch("app.routes.commands.chrome.open_url") as open_url:
            result = execute_command(CommandRequest(command="teach me about machine learning"))

        self.assertEqual(result, {"handled": False})
        open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
