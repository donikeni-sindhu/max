from uuid import UUID

from pydantic import BaseModel, Field

from app.agent.demo_data import CONCEPTS
from app.agent.events import emit
from app.agent.llm import complete_json
from app.models import ConceptDraft


class PrerequisitePlan(BaseModel):
    concepts: list[ConceptDraft] = Field(default_factory=list)


def _fallback(names: list[str]) -> PrerequisitePlan:
    known = {str(row["name"]).lower(): row for row in CONCEPTS}
    concepts: list[ConceptDraft] = []
    ordered = names or [str(row["name"]) for row in CONCEPTS]
    for index, name in enumerate(ordered, start=1):
        row = known.get(name.lower())
        if row:
            concepts.append(ConceptDraft.model_validate(row))
            continue
        level = 1 if index <= 3 else 2 if index <= 5 else 3
        concepts.append(
            ConceptDraft(
                name=name,
                level=level,
                explanation=f"{name} is a building block you need before the paper will make sense.",
                order_index=index,
                status="active" if index == 1 else "pending",
            )
        )
    return PrerequisitePlan(concepts=concepts)


def build_prerequisites(mission_id: UUID, concept_names: list[str]) -> PrerequisitePlan:
    emit(mission_id, "prereqs_found", "Ordering prerequisite concepts", {"names": concept_names})
    result = _fallback(concept_names)
    try:
        result = complete_json(
            "Turn these concepts into a learning sequence with levels 1 foundations, "
            "2 core, 3 target paper. JSON: {\"concepts\": [{\"name\",\"level\",\"explanation\","
            "\"order_index\",\"status\"}]}. status is active for the first and pending after. "
            f"Concepts: {concept_names}",
            PrerequisitePlan,
        )
        if not result.concepts:
            result = _fallback(concept_names)
    except Exception:
        result = _fallback(concept_names)
    emit(mission_id, "prereqs_found", f"{len(result.concepts)} prerequisites are ready", {"count": len(result.concepts)})
    return result
