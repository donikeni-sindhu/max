from uuid import UUID

from pydantic import BaseModel, Field

from app.agent.events import emit
from app.agent.llm import complete_json

DEFAULT_STEPS = [
    "intent",
    "plan",
    "open_paper",
    "analyze_paper",
    "prerequisites",
    "web_research",
    "learning_path",
]


class Plan(BaseModel):
    steps: list[str] = Field(default_factory=lambda: list(DEFAULT_STEPS))


def build_plan(mission_id: UUID, target_title: str) -> Plan:
    emit(mission_id, "searching", "Planning the research steps", {"target_title": target_title})
    plan = Plan()
    try:
        plan = complete_json(
            "Return JSON {\"steps\": [...]} with the ordered research steps for a paper: "
            + ", ".join(DEFAULT_STEPS)
            + f". Target: {target_title}",
            Plan,
        )
    except Exception:
        plan = Plan()
    emit(mission_id, "searching", "Research plan is ready", {"steps": plan.steps})
    return plan
