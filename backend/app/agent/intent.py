import os
import re
from uuid import UUID

from pydantic import BaseModel

from app.agent.demo_data import PAPER_TITLE
from app.agent.events import emit
from app.agent.llm import complete_json


class IntentResult(BaseModel):
    goal_type: str
    target_title: str


def _fallback(goal: str) -> IntentResult:
    quoted = re.search(r"['\"]([^'\"]+)['\"]", goal)
    if quoted:
        return IntentResult(goal_type="paper", target_title=quoted.group(1))
    if "paper" in goal.lower():
        return IntentResult(goal_type="paper", target_title=PAPER_TITLE)
    return IntentResult(goal_type="topic", target_title=goal.strip() or "Untitled goal")


def parse_goal(mission_id: UUID, goal: str) -> IntentResult:
    emit(mission_id, "goal_detected", "Reading the learning goal", {"goal": goal})
    result = _fallback(goal)
    if os.getenv("REBORN_SKIP_UI") != "1":
        try:
            result = complete_json(
                "Classify this learning goal. JSON keys: goal_type (paper or topic), target_title. "
                f"Goal: {goal}",
                IntentResult,
            )
        except Exception:
            result = _fallback(goal)
    emit(mission_id, "goal_detected", f"Goal is about {result.target_title}", result.model_dump())
    return result
