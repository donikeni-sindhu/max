"""Run a mission from goal to learning path, then advance one concept at a time."""

from __future__ import annotations

import os
import random
import logging
from uuid import UUID

from app import db
from app.agent import chat, intent, launcher, learning_path, mission_control, paper_analyzer, pdf_reader, planner, prerequisites, web_research
from app.agent.demo_data import CONCEPTS, DEMO_GOAL, PAPER_PDF, PAPER_TITLE, RESOURCES
from app.agent.events import emit
from app.agent.uia import chrome, executor, observer
from app.config import get_settings
from app.models import MissionSummary

_logger = logging.getLogger(__name__)


def demo_pause(mission_id: UUID) -> None:
    if os.getenv("REBORN_FAST") == "1" or not get_settings().demo_mode:
        return
    # Event.wait makes optional demo pacing interruptible instead of delaying Cancel for several seconds.
    if mission_control.is_cancelled(mission_id):
        raise mission_control.MissionCancelled("Mission was cancelled")
    state = random.uniform(2, 4)
    if mission_control.wait_or_cancel(mission_id, state):
        raise mission_control.MissionCancelled("Mission was cancelled")


def _check_cancelled(mission_id: UUID) -> None:
    # Every phase boundary checks the flag because HTTP/model calls may finish after a cancel request.
    if mission_control.is_cancelled(mission_id):
        raise mission_control.MissionCancelled("Mission was cancelled")


def _apply_demo(mission_id: UUID, goal: str, target_title: str) -> None:
    concepts = db.replace_concepts(mission_id, CONCEPTS)
    db.replace_resources(mission_id, RESOURCES)
    names = [str(row["name"]) for row in concepts]
    learning_path.publish_path(mission_id, goal, target_title, PAPER_PDF, "", names)


def run(mission_id: UUID, goal: str, reserved: bool = False) -> None:
    # API routes reserve before queueing; direct callers still acquire the same per-mission lock here.
    if not reserved and not mission_control.reserve_run(mission_id):
        emit(mission_id, "run_ignored", "This mission is already running", {})
        return
    try:
        if os.getenv("REBORN_SKIP_UI") != "1":
            observer.start(mission_id)
        _run_once(mission_id, goal)
    except mission_control.MissionCancelled as exc:
        db.update_mission(mission_id, status="cancelled")
        emit(mission_id, "mission_cancelled", str(exc), {})
    except Exception as exc:
        # Replaying the whole pipeline would repeat browser side effects; preserve the real failure instead.
        _logger.exception("Mission %s failed", mission_id)
        emit(mission_id, "error", f"Mission failed: {exc}", {"detail": str(exc)})
        if get_settings().demo_mode and goal.strip().casefold() == DEMO_GOAL.casefold():
            _apply_demo(mission_id, goal, PAPER_TITLE)
            emit(mission_id, "demo_fallback", f"DEMO MODE used the cached paper path after: {exc}", {"detail": str(exc)})
        else:
            db.update_mission(mission_id, status="failed")
    finally:
        observer.stop(mission_id)
        mission_control.release_run(mission_id)


def _run_once(mission_id: UUID, goal: str) -> None:
    _check_cancelled(mission_id)
    db.update_mission(mission_id, status="planning", goal=goal)
    parsed = intent.parse_goal(mission_id, goal)
    _check_cancelled(mission_id)
    # Open apps through the verified strategy ladder rather than asking UIA to find a missing app window.
    if parsed.goal_type == "open_app":
        if not parsed.target_app:
            raise RuntimeError("Name the app you want to open")
        db.update_mission(mission_id, status="researching")
        opened = launcher.launch_app(parsed.target_app, mission_id)
        if not opened.get("ok"):
            raise RuntimeError(str(opened.get("detail") or f"Could not open {parsed.target_app}"))
        db.update_mission(mission_id, status="complete")
        return
    # Keep current-window UI commands and chat separate from the paper-only research pipeline.
    if parsed.goal_type == "ui_command":
        db.update_mission(mission_id, status="researching")
        executor.run_command(goal, mission_id)
        return
    if parsed.goal_type == "chat":
        response = chat.answer(goal)
        emit(mission_id, "chat_response", response, {"request": goal})
        db.update_mission(mission_id, status="complete")
        return
    if not parsed.target_title:
        raise RuntimeError("Name the paper you want to study so REBORN does not guess a title")
    demo_pause(mission_id)
    db.update_mission(mission_id, target_title=parsed.target_title, status="planning")
    planner.build_plan(mission_id, parsed.target_title)
    _check_cancelled(mission_id)
    demo_pause(mission_id)
    db.update_mission(mission_id, status="researching")
    emit(mission_id, "searching", f"Opening {parsed.target_title}", {})
    paper = {"ok": False, "url": "", "tab": parsed.target_title}
    if os.getenv("REBORN_SKIP_UI") != "1":
        paper = chrome.open_paper_pdf(parsed.target_title, mission_id)
        if paper.get("skipped"):
            # Replay may reuse the already-open paper URL without causing a duplicate browser navigation.
            state = ((db.get_bundle(mission_id) or {}).get("world_state") or {}).get("state") or {}
            prior_pdf = state.get("pdf") or {}
            paper = {"ok": bool(prior_pdf.get("url")), "url": prior_pdf.get("url", ""), "tab": (state.get("browser") or {}).get("tab")}
    if not paper.get("ok") and os.getenv("REBORN_SKIP_UI") != "1":
        raise RuntimeError(str(paper.get("detail") or f"Could not open {parsed.target_title}"))
    emit(mission_id, "paper_found", f"Found {parsed.target_title}", {"url": paper.get("url")})
    demo_pause(mission_id)
    pdf_url = str(paper.get("url") or PAPER_PDF)
    extracted = pdf_reader.extract_pdf(pdf_url)
    db.patch_world(
        mission_id,
        target_paper={"title": parsed.target_title, "url": pdf_url.replace("/pdf/", "/abs/")},
        pdf={"url": pdf_url, "title": parsed.target_title, "text_excerpt": extracted["excerpt"][:500]},
        browser={"open": True, "url": pdf_url, "title": parsed.target_title, "tab": paper.get("tab"), "tabs": [], "active_tab": paper.get("tab")},
    )
    analysis = paper_analyzer.analyze_paper(mission_id, extracted["excerpt"])
    _check_cancelled(mission_id)
    demo_pause(mission_id)
    plan = prerequisites.build_prerequisites(mission_id, analysis.concepts)
    saved = db.replace_concepts(mission_id, [concept.model_dump() for concept in plan.concepts])
    demo_pause(mission_id)
    hits = web_research.research_concepts(mission_id, [str(row["name"]) for row in saved], goal)
    db.replace_resources(mission_id, [hit.model_dump() for hit in hits])
    demo_pause(mission_id)
    learning_path.publish_path(
        mission_id,
        goal,
        parsed.target_title,
        pdf_url,
        extracted["excerpt"],
        [str(row["name"]) for row in saved],
    )


def advance(mission_id: UUID) -> dict[str, str]:
    _check_cancelled(mission_id)
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
        url = str(resource["url"]) if resource else ""
        if resource and os.getenv("REBORN_SKIP_UI") != "1":
            opened = chrome.open_resource(url, nxt["name"], mission_id)
            if not opened.get("ok") and not opened.get("skipped"):
                emit(mission_id, "error", f"Could not open resource for {nxt['name']}", {"detail": opened.get("detail", "")})
                db.update_mission(mission_id, status="failed")
                return {"status": "failed", "detail": str(opened.get("detail") or "Resource could not be opened")}
            if opened.get("skipped"):
                emit(mission_id, "url_skipped", f"Skipped the already-open resource for {nxt['name']}", {"url": url})
        if resource:
            emit(mission_id, "analyzing", nxt["explanation"], {"concept": nxt["name"], "url": url})
        else:
            emit(mission_id, "resource_missing", f"No resource is available for {nxt['name']}; skipped opening a page", {"concept": nxt["name"]})
        db.patch_world(mission_id, current_knowledge=nxt["explanation"])
        db.update_mission(mission_id, status="learning")
        return {"status": "learning", "concept": nxt["name"]}
    tab = ""
    world = (bundle.get("world_state") or {}).get("state") or {}
    browser = world.get("browser") or {}
    tab = str(browser.get("tab") or browser.get("active_tab") or PAPER_TITLE)
    if os.getenv("REBORN_SKIP_UI") != "1":
        focused = chrome.focus_tab(tab, mission_id)
        if not focused.get("ok"):
            emit(mission_id, "browser_focus_failed", "Could not return to the paper tab; leaving the current page open", {"detail": focused.get("detail", "")})
    _check_cancelled(mission_id)
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
