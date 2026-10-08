import os
from uuid import UUID

from pydantic import BaseModel

from app.agent.demo_data import RESOURCES
from app.agent.events import emit
from app.agent.uia import chrome


class ResearchHit(BaseModel):
    concept_name: str
    title: str
    url: str
    source: str
    score: float
    selected: bool = True


def _score(title: str, url: str) -> float:
    score = 0.45
    lowered = f"{title} {url}".lower()
    if "arxiv.org" in lowered or ".edu" in lowered:
        score += 0.25
    if any(word in lowered for word in ("illustrated", "intro", "beginner", "visual", "explained")):
        score += 0.2
    return min(score, 0.99)


def _source(url: str) -> str:
    if "arxiv.org" in url:
        return "arxiv"
    if ".edu" in url:
        return "edu"
    return "web"


def _demo_for(name: str) -> ResearchHit | None:
    for row in RESOURCES:
        if str(row["concept_name"]).lower() == name.lower():
            return ResearchHit.model_validate(row)
    return None


def research_concepts(mission_id: UUID, concept_names: list[str]) -> list[ResearchHit]:
    emit(mission_id, "researching", "Searching for beginner resources", {"concepts": concept_names})
    hits: list[ResearchHit] = []
    skip_ui = os.getenv("REBORN_SKIP_UI") == "1"
    for name in concept_names:
        chosen: ResearchHit | None = None
        if not skip_ui:
            found = chrome.search(f"{name} explained for beginners")
            ranked = []
            for item in found.get("results") or []:
                url = str(item.get("url") or "")
                title = str(item.get("title") or name)
                if not url.startswith("http"):
                    continue
                ranked.append(( _score(title, url), title, url))
            ranked.sort(reverse=True)
            if ranked:
                score, title, url = ranked[0]
                chosen = ResearchHit(
                    concept_name=name,
                    title=title,
                    url=url,
                    source=_source(url),
                    score=score,
                )
        if chosen is None:
            chosen = _demo_for(name) or ResearchHit(
                concept_name=name,
                title=name,
                url="https://arxiv.org/abs/1706.03762",
                source="arxiv",
                score=0.8,
            )
        hits.append(chosen)
    emit(mission_id, "researching", f"Chose {len(hits)} resources", {"count": len(hits)})
    return hits
