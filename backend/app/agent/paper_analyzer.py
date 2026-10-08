from uuid import UUID

from pydantic import BaseModel, Field

from app.agent.demo_data import CONCEPTS
from app.agent.events import emit
from app.agent.llm import complete_json


class PaperAnalysis(BaseModel):
    concepts: list[str] = Field(default_factory=list)
    excerpt: str = ""


def analyze_paper(mission_id: UUID, text: str) -> PaperAnalysis:
    emit(mission_id, "analyzing", "Looking for concepts the paper depends on", {})
    fallback = PaperAnalysis(concepts=[str(row["name"]) for row in CONCEPTS], excerpt=text[:400])
    result = fallback
    try:
        result = complete_json(
            "From this paper text, list the main concepts a beginner must learn first. "
            'JSON: {"concepts": ["name"], "excerpt": "one sentence"}. Text:\n'
            + text[:2500],
            PaperAnalysis,
        )
        if not result.concepts:
            result = fallback
    except Exception:
        result = fallback
    emit(mission_id, "analyzing", f"Found {len(result.concepts)} concepts", {"concepts": result.concepts})
    return result
