"""Strict JSON calls to Groq. Callers handle provider errors at their mission boundary."""

from __future__ import annotations

import logging
import random
import time
from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)
_logger = logging.getLogger(__name__)
_MAX_REQUEST_RETRIES = 2


def _error_code(error: Exception) -> int | None:
    # Groq's SDK exposes HTTPStatusError.status_code on APIStatusError subclasses.
    try:
        return int(getattr(error, "status_code", 0)) or None
    except (TypeError, ValueError):
        return None


def complete_json(prompt: str, model: type[T], max_output_tokens: int = 1200) -> T:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    from groq import Groq

    # Disable SDK retries so the bounded, status-aware retry below is the only retry policy.
    client = Groq(api_key=settings.groq_api_key, max_retries=0)
    response = None
    try:
        for attempt in range(_MAX_REQUEST_RETRIES + 1):
            try:
                response = client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt + "\nReturn one JSON object matching the required schema.",
                        }
                    ],
                    max_completion_tokens=max_output_tokens,
                    reasoning_effort="low",
                    response_format={"type": "json_object"},
                )
                break
            except Exception as exc:
                code = _error_code(exc)
                # Retry only temporary server failures. Invalid keys, malformed requests, and quota
                # errors need a user-visible fix, while replaying the whole mission could repeat UI actions.
                if code not in {500, 502, 503, 504} or attempt >= _MAX_REQUEST_RETRIES:
                    raise
                delay = (2**attempt) + random.uniform(0, 0.5)
                _logger.warning(
                    "Groq returned temporary HTTP %s; retrying request %s/%s in %.1f seconds",
                    code,
                    attempt + 1,
                    _MAX_REQUEST_RETRIES,
                    delay,
                )
                time.sleep(delay)
    finally:
        # Each call is stateless; close its HTTP transports so repeated missions do not leak sockets.
        client.close()
    text = response.choices[0].message.content if response and response.choices else None
    if not text:
        raise ValueError("Groq did not return a JSON response")
    # JSON mode removes markdown wrappers; Pydantic validates the expected shape before use.
    return model.model_validate_json(text)
