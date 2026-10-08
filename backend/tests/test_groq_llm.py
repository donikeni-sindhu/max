import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import BaseModel

from app.agent import llm


class Answer(BaseModel):
    answer: str


def completion(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class TemporaryUnavailable(Exception):
    status_code = 503


class GroqLlmTests(unittest.TestCase):
    def make_client(self, create):
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=Mock(),
        )

    def test_json_completion_uses_groq_json_mode_and_closes_client(self):
        create = Mock(return_value=completion('{"answer":"ok"}'))
        client = self.make_client(create)
        with (
            patch.object(llm, "get_settings", return_value=SimpleNamespace(groq_api_key="test-key", groq_model="groq-test")),
            patch("groq.Groq", return_value=client) as create_client,
        ):
            result = llm.complete_json("Say ok", Answer, max_output_tokens=123)

        self.assertEqual(result.answer, "ok")
        create_client.assert_called_once_with(api_key="test-key", max_retries=0)
        call = create.call_args.kwargs
        self.assertEqual(call["model"], "groq-test")
        self.assertEqual(call["max_completion_tokens"], 123)
        self.assertEqual(call["reasoning_effort"], "low")
        self.assertEqual(call["response_format"], {"type": "json_object"})
        self.assertIn("JSON object", call["messages"][0]["content"])
        client.close.assert_called_once_with()

    def test_temporary_503_is_retried_with_backoff(self):
        create = Mock(side_effect=[TemporaryUnavailable("busy"), completion('{"answer":"ok"}')])
        client = self.make_client(create)
        with (
            patch.object(llm, "get_settings", return_value=SimpleNamespace(groq_api_key="test-key", groq_model="groq-test")),
            patch("groq.Groq", return_value=client),
            patch.object(llm.time, "sleep") as sleep,
            patch.object(llm.random, "uniform", return_value=0.25),
        ):
            result = llm.complete_json("Say ok", Answer)

        self.assertEqual(result.answer, "ok")
        self.assertEqual(create.call_count, 2)
        sleep.assert_called_once_with(1.25)
        client.close.assert_called_once_with()

    def test_client_error_is_not_retried(self):
        bad_request = Exception("bad request")
        bad_request.status_code = 400
        create = Mock(side_effect=bad_request)
        client = self.make_client(create)
        with (
            patch.object(llm, "get_settings", return_value=SimpleNamespace(groq_api_key="test-key", groq_model="groq-test")),
            patch("groq.Groq", return_value=client),
            patch.object(llm.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(Exception, "bad request"):
                llm.complete_json("Say ok", Answer)

        self.assertEqual(create.call_count, 1)
        sleep.assert_not_called()
        client.close.assert_called_once_with()

    def test_missing_groq_key_is_reported_without_constructing_client(self):
        with (
            patch.object(llm, "get_settings", return_value=SimpleNamespace(groq_api_key="")),
            patch("groq.Groq") as create_client,
        ):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                llm.complete_json("Say ok", Answer)
        create_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
