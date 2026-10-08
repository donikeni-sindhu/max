"""Route app launches, current-window UI commands, explicit paper missions, and chat to separate handlers."""

from __future__ import annotations

import logging
import re
from typing import Literal
from uuid import UUID

from groq import APIError
from pydantic import BaseModel, ValidationError

from app.agent import apps
from app.agent.commands import parse_open_command
from app.agent.events import emit
from app.agent.llm import complete_json
from app.config import get_settings

_logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """Keep route names explicit so command handlers cannot fall into the paper pipeline by accident."""

    goal_type: Literal["open_app", "ui_command", "paper_mission", "chat"]
    target_title: str = ""
    target_app: str = ""
    response: str = ""


_OPEN_APP = re.compile(r"^\s*(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(.+?)\s*[.!?]*$", re.IGNORECASE)
_PAPER_TOPIC = re.compile(r"\b(?:paper|research article)\s+(?:on|about|titled|called)\s+(.+?)\s*[.!?]*$", re.IGNORECASE)
_PAPER_TASK = re.compile(r"\b(learn|understand|read|summarize|analyse|analyze|explain|research|find|give|show)\b", re.IGNORECASE)
_EXPLICIT_PAPER = re.compile(
    r"\b(?:the|this|that|my)\s+(?:research\s+)?paper\b|\b(?:paper|research article)\s+(?:on|about|titled|called)\b|\bresearch article\b|\bpaper\s*[.!?]*$",
    re.IGNORECASE,
)
_ACTION_VERB = re.compile(
    r"\b(click|type|press|scroll|search|find|select|switch|close|back|forward|reload|refresh|navigate)\b",
    re.IGNORECASE,
)


def _quoted_title(goal: str) -> str:
    """Extract a title only when the user marked its boundaries with quotes."""

    match = re.search(r"['\"]([^'\"]+)['\"]", goal)
    return match.group(1).strip() if match else ""


def _fallback(goal: str) -> IntentResult:
    """Classify common requests deterministically when Groq is unavailable, without guessing a demo paper."""

    text = goal.strip()
    # Known websites remain direct browser commands instead of being mistaken for executable app names.
    if parse_open_command(text):
        return IntentResult(goal_type="ui_command")
    open_match = _OPEN_APP.fullmatch(text)
    if open_match:
        target = open_match.group(1).strip().strip(" \"'")
        topic = _PAPER_TOPIC.search(target)
        if topic:
            return IntentResult(goal_type="paper_mission", target_title=topic.group(1).strip(" \"'"))
        if re.match(r"^(?:the\s+)?paper\s*$", target, re.IGNORECASE):
            return IntentResult(goal_type="paper_mission", target_title=_quoted_title(text))
        if "." in target or target.startswith(("http://", "https://")):
            return IntentResult(goal_type="ui_command")
        # A registry alias improves display but arbitrary app names remain valid launch targets.
        spec = apps.lookup(target)
        return IntentResult(goal_type="open_app", target_app=spec.name if spec else target)

    paper_topic = _PAPER_TOPIC.search(text)
    if paper_topic and (_PAPER_TASK.search(text) or re.search(r"\b(open|show)\b", text, re.IGNORECASE)):
        return IntentResult(goal_type="paper_mission", target_title=paper_topic.group(1).strip(" \"'"))
    if (_EXPLICIT_PAPER.search(text) or _quoted_title(text)) and _PAPER_TASK.search(text):
        title = _quoted_title(text)
        return IntentResult(goal_type="paper_mission", target_title=title)
    if _ACTION_VERB.search(text):
        return IntentResult(goal_type="ui_command")
    return IntentResult(goal_type="chat")


def parse_goal(mission_id: UUID, goal: str) -> IntentResult:
    """Use Groq when configured, then fall back to deterministic rules with no generic-paper substitution."""

    emit(mission_id, "goal_detected", "Classifying the request", {"goal": goal})
    result = _fallback(goal)
    if get_settings().groq_api_key:
        try:
            result = complete_json(
                "Classify the request as exactly one goal_type: open_app, ui_command, paper_mission, or chat. "
                "Use open_app for open/launch/start plus an app name, including unknown app names. "
                "Use ui_command for actions in the currently open app or browser. "
                "Use paper_mission only for a specific paper title or a paper explicitly requested on/about a topic; "
                "never substitute a default or demo paper. The word paper alone is not a paper request. "
                "Use chat for ordinary questions or statements. Return target_app only for open_app, "
                "target_title only for a user-named paper or explicit paper topic, and response only for chat. "
                f"Request: {goal}",
                IntentResult,
                max_output_tokens=400,
            )
        except (APIError, ValidationError, ValueError, RuntimeError) as exc:
            _logger.warning("Intent classification used local rules after %s", type(exc).__name__)
            result = _fallback(goal)
    deterministic = _fallback(goal)
    if deterministic.goal_type in {"open_app", "ui_command", "paper_mission"} and result.goal_type != deterministic.goal_type:
        # Preserve explicit commands and reject paper guesses for generic phrases such as `paper airplane`.
        result = deterministic
    if result.goal_type == "paper_mission" and not result.target_title and deterministic.target_title:
        result = result.model_copy(update={"target_title": deterministic.target_title})
    if result.goal_type == "open_app" and not result.target_app:
        result = _fallback(goal)
    emit(mission_id, "goal_detected", f"Request routed to {result.goal_type}", result.model_dump())
    return result
