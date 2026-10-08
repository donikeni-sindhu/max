import os
import re
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.agent.events import emit
from app.agent.uia import chrome
from app.config import get_settings


class ResearchHit(BaseModel):
    concept_name: str
    title: str
    url: str
    source: str
    score: float
    selected: bool = True


KNOWN_BLOG_DOMAINS = ("jalammar.github.io", "distill.pub", "huggingface.co", "pytorch.org")


def _score(title: str, url: str) -> float:
    # Source quality gets the dominant weight; title wording cannot outweigh an authoritative domain.
    host = (urlsplit(url).hostname or "").lower()
    score = 0.45
    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        score = 0.95
    elif host.endswith(".edu"):
        score = 0.90
    elif any(host == domain or host.endswith(f".{domain}") for domain in KNOWN_BLOG_DOMAINS):
        score = 0.82
    # A small wording bonus helps order similar sources without making clickbait win on its own.
    if any(word in title.lower() for word in ("illustrated", "intro", "beginner", "visual", "explained")):
        score += 0.02
    return min(score, 0.99)


def _source(url: str) -> str:
    if "arxiv.org" in url:
        return "arxiv"
    if ".edu" in url:
        return "edu"
    return "web"


def _blocked(url: str, blocklist: tuple[str, ...]) -> bool:
    # Match whole host suffixes so a fake host like youtube.com.example.org is not blocked by accident.
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in blocklist)


def research_concepts(mission_id: UUID, concept_names: list[str], goal: str = "") -> list[ResearchHit]:
    emit(mission_id, "researching", "Searching for beginner resources", {"concepts": concept_names})
    hits: list[ResearchHit] = []
    skip_ui = os.getenv("REBORN_SKIP_UI") == "1"
    settings = get_settings()
    blocked = tuple(domain.strip().lower().lstrip(".") for domain in settings.blocked_domains.split(",") if domain.strip())
    # Video sites are allowed only when the user's original request asks for video content.
    allow_video = bool(re.search(r"\b(?:youtube|youtu\.be|video|videos)\b", goal, re.IGNORECASE))
    for name in concept_names:
        chosen: ResearchHit | None = None
        if not skip_ui:
            found = chrome.search(f"{name} explained for beginners", mission_id)
            ranked = []
            for item in found.get("results") or []:
                url = str(item.get("url") or "")
                title = str(item.get("title") or name)
                if not url.startswith(("http://", "https://")):
                    continue
                if not allow_video and _blocked(url, blocked):
                    continue
                ranked.append((_score(title, url), title, url))
            ranked.sort(key=lambda row: row[0], reverse=True)
            # Filtering happens before ranking so a blocked top result cannot win selection.
            if ranked:
                score, title, url = ranked[0]
                chosen = ResearchHit(
                    concept_name=name,
                    title=title,
                    url=url,
                    source=_source(url),
                    score=score,
                )
        if chosen is not None:
            hits.append(chosen)
    emit(mission_id, "researching", f"Chose {len(hits)} resources", {"count": len(hits)})
    return hits
