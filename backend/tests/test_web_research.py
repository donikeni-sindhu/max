import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.agent import web_research


class WebResearchTests(unittest.TestCase):
    def test_blocks_youtube_and_its_subdomains(self):
        blocked = ("youtube.com", "youtu.be", "m.youtube.com")
        self.assertTrue(web_research._blocked("https://www.youtube.com/watch?v=1", blocked))
        self.assertTrue(web_research._blocked("https://music.youtube.com/", blocked))
        self.assertFalse(web_research._blocked("https://youtube.com.example.org/", blocked))

    def test_source_quality_beats_explainer_keywords(self):
        self.assertGreater(
            web_research._score("A paper explained for beginners", "https://arxiv.org/abs/1234"),
            web_research._score("Beginner video explained visually", "https://www.youtube.com/watch?v=1"),
        )

    def test_selects_best_unblocked_result(self):
        mission_id = uuid4()
        results = {
            "ok": True,
            "results": [
                {"title": "Visual explanation", "url": "https://www.youtube.com/watch?v=1"},
                {"title": "Research paper", "url": "https://arxiv.org/abs/1234"},
            ],
        }
        with (
            patch.dict("os.environ", {"REBORN_SKIP_UI": "0"}),
            patch.object(web_research, "get_settings", return_value=SimpleNamespace(blocked_domains="youtube.com,youtu.be,m.youtube.com")),
            patch.object(web_research.chrome, "search", return_value=results),
            patch.object(web_research, "emit"),
        ):
            hits = web_research.research_concepts(mission_id, ["Attention"], "Learn this paper")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://arxiv.org/abs/1234")

    def test_returns_no_hit_instead_of_a_fake_arxiv_resource(self):
        with (
            patch.dict("os.environ", {"REBORN_SKIP_UI": "1"}),
            patch.object(web_research, "emit"),
        ):
            hits = web_research.research_concepts(uuid4(), ["Unmatched concept"])

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
