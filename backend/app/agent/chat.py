"""Small text-only response path for requests that are not browser actions or paper missions."""

from pydantic import BaseModel

from app.agent.llm import complete_json
from app.config import get_settings


class ChatResponse(BaseModel):
    text: str


def answer(request: str) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        # A clear capability response is more useful than inventing factual answers with no language model configured.
        return "I can open websites and guide paper-learning missions. Try ‘Open github.com’ or ask me to explain a paper."
    result = complete_json(
        "Answer the user's question briefly and clearly. Return JSON {\"text\": \"answer\"}. "
        f"Question: {request}",
        ChatResponse,
    )
    return result.text
