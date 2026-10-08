"""Strict JSON calls to Claude. Callers fall back when this raises."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


def complete_json(prompt: str, model: type[T]) -> T:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1200,
        messages=[
            {
                "role": "user",
                "content": prompt + "\nReply with one JSON object only. Do not add markdown.",
            }
        ],
    )
    text = "".join(getattr(block, "text", "") for block in message.content)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return JSON")
    return model.model_validate(json.loads(text[start : end + 1]))
