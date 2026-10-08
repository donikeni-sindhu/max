"""Run a mission from goal to learning path, then advance one concept at a time."""

from __future__ import annotations

import os
import random
import time
from uuid import UUID

from app import db
from app.agent import intent, learning_path, paper_analyzer, pdf_reader, planner, prerequisites, web_research
from app.agent.demo_data import CONCEPTS, PAPER_PDF, PAPER_TITLE, RESOURCES
from app.agent.events import emit
from app.agent.uia import chrome, observer
from app.agent.fallback import browser as playwright_browser
from app.config import get_settings
from app.models import MissionSummary


def demo_pause() -> None:
    if os.getenv("REBORN_FAST") == "1" or not get_settings().demo_mode:
        return
    time.sleep(random.uniform(2, 4))


def _apply_demo(mission_id: UUID, goal: str, target_title: str) -> None:
    concepts = db.replace_concepts(mission_id, CONCEPTS)
    db.replace_resources(mission_id, RESOURCES)
    names = [str(row["name"]) for row in concepts]
    learning_path.publish_path(mission_id, goal, target_title, PAPER_PDF, "", names)


def run(mission_id: UUID, goal: str) -> None:
    if os.getenv("REBORN_SKIP_UI") != "1":
        observer.start(mission_id)
    try:
        _run_once(mission_id, goal)
    except Exception as exc:
        try:
            _run_once(mission_id, goal)
        except Exception as again:
            emit(mission_id, "error", "The mission step failed", {"detail": str(again or exc)})
            if get_settings().demo_mode:
                _apply_demo(mission_id, goal, PAPER_TITLE)
            else:
                db.update_mission(mission_id, status="failed")
    finally:
        observer.stop(mission_id)


def _run_once(mission_id: UUID, goal: str) -> None:
    db.update_mission(mission_id, status="planning", goal=goal)
    parsed = intent.parse_goal(mission_id, goal)
    demo_pause()
    db.update_mission(mission_id, target_title=parsed.target_title, status="planning")
    planner.build_plan(mission_id, parsed.target_title)
    demo_pause()
    db.update_mission(mission_id, status="researching")
    emit(mission_id, "searching", f"Opening {parsed.target_title}", {})
    paper = {"ok": False, "url": PAPER_PDF, "tab": parsed.target_title}
    if os.getenv("REBORN_SKIP_UI") != "1":
        paper = chrome.open_paper_pdf(parsed.target_title)
        if not paper.get("ok"):
            paper = playwright_browser.open_url(PAPER_PDF)
    emit(mission_id, "paper_found", f"Found {parsed.target_title}", {"url": paper.get("url")})
    demo_pause()
    pdf_url = str(paper.get("url") or PAPER_PDF)
    extracted = pdf_reader.extract_pdf(pdf_url)
    db.patch_world(
        mission_id,
        target_paper={"title": parsed.target_title, "url": pdf_url.replace("/pdf/", "/abs/")},
        pdf={"url": pdf_url, "title": parsed.target_title, "text_excerpt": extracted["excerpt"][:500]},
        browser={"open": True, "url": pdf_url, "title": parsed.target_title, "tab": paper.get("tab"), "tabs": [], "active_tab": paper.get("tab")},
    )
    analysis = paper_analyzer.analyze_paper(mission_id, extracted["excerpt"])
    demo_pause()
    plan = prerequisites.build_prerequisites(mission_id, analysis.concepts)
    saved = db.replace_concepts(mission_id, [concept.model_dump() for concept in plan.concepts])
    demo_pause()
    hits = web_research.research_concepts(mission_id, [str(row["name"]) for row in saved])
    db.replace_resources(mission_id, [hit.model_dump() for hit in hits])
    demo_pause()
    learning_path.publish_path(
        mission_id,
        goal,
        parsed.target_title,
        pdf_url,
        extracted["excerpt"],
        [str(row["name"]) for row in saved],
    )


def advance(mission_id: UUID) -> dict[str, str]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        return {"status": "missing"}
    concepts = bundle["concepts"]
    active = next((row for row in concepts if row["status"] == "active"), None)
    pending = [row for row in concepts if row["status"] == "pending"]
    if active is not None:
        db.update_concept_status(active["id"], "done")
    if pending:
        nxt = pending[0]
        db.update_concept_status(nxt["id"], "active")
        resource = next((row for row in bundle["resources"] if row.get("concept_id") == nxt["id"]), None)
        url = resource["url"] if resource else PAPER_PDF
        if os.getenv("REBORN_SKIP_UI") != "1":
            opened = chrome.open_resource(url, nxt["name"])
            if not opened.get("ok"):
                playwright_browser.open_url(url)
        emit(mission_id, "analyzing", nxt["explanation"], {"concept": nxt["name"], "url": url})
        db.patch_world(mission_id, current_knowledge=nxt["explanation"])
        db.update_mission(mission_id, status="learning")
        return {"status": "learning", "concept": nxt["name"]}
    tab = ""
    world = (bundle.get("world_state") or {}).get("state") or {}
    browser = world.get("browser") or {}
    tab = str(browser.get("tab") or browser.get("active_tab") or PAPER_TITLE)
    if os.getenv("REBORN_SKIP_UI") != "1":
        focused = chrome.focus_tab(tab)
        if not focused.get("ok"):
            chrome.open_url(str((world.get("pdf") or {}).get("url") or PAPER_PDF))
    explored = len(bundle["resources"])
    identified = len(concepts)
    summary = MissionSummary(
        resources_explored=explored,
        concepts_identified=identified,
        ready_to_read=True,
    )
    db.patch_world(mission_id, summary=summary.model_dump())
    db.update_mission(mission_id, status="complete")
    emit(
        mission_id,
        "path_ready",
        "Research mission complete. The paper is ready to read.",
        summary.model_dump(),
    )
    return {"status": "complete"}
