from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app import db
from app.agent import orchestrator
from app.agent import mission_control
from app.agent.events import emit
from app.agent import safety
from app.models import DEMO_USER_ID

router = APIRouter(tags=["missions"])


class CreateMission(BaseModel):
    goal: str
    user_id: UUID | None = None


class ConfirmBody(BaseModel):
    approved: bool


@router.post("/missions")
def create_mission(body: CreateMission, background: BackgroundTasks) -> dict[str, str]:
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")
    user_id = body.user_id or DEMO_USER_ID
    try:
        mission = db.create_mission(user_id, goal)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not create mission: {exc}") from exc
    mission_id = UUID(str(mission["id"]))
    # Reserve synchronously so a second request cannot race the background worker startup.
    if not mission_control.reserve_run(mission_id):
        raise HTTPException(status_code=409, detail="This mission is already running")
    background.add_task(orchestrator.run, mission_id, goal, True)
    return {"id": str(mission_id)}


@router.get("/missions/{mission_id}")
def read_mission(mission_id: UUID) -> dict[str, object]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    user_id = str(bundle["mission"]["user_id"])
    return {
        "mission": bundle["mission"],
        "concepts": bundle["concepts"],
        "resources": bundle["resources"],
        "world_state": bundle["world_state"],
        "events": bundle.get("events", []),
        "character": db.get_character(user_id),
    }


@router.post("/missions/{mission_id}/next")
def next_concept(mission_id: UUID) -> dict[str, str]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    # Advancing also drives Chrome, so it shares the run lock with mission creation and replay.
    if not mission_control.reserve_run(mission_id):
        raise HTTPException(status_code=409, detail="This mission is already running")
    try:
        return orchestrator.advance(mission_id)
    finally:
        mission_control.release_run(mission_id)


@router.post("/missions/{mission_id}/replay")
def replay_mission(mission_id: UUID, background: BackgroundTasks) -> dict[str, str]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    goal = str(bundle["mission"]["goal"])
    # The shared lock prevents duplicate replay workers from repeating UI side effects.
    if not mission_control.reserve_run(mission_id):
        raise HTTPException(status_code=409, detail="This mission is already running")
    background.add_task(orchestrator.run, mission_id, goal, True)
    return {"id": str(mission_id), "status": "replay"}


@router.post("/missions/{mission_id}/cancel")
def cancel_mission(mission_id: UUID) -> dict[str, bool]:
    if db.get_bundle(mission_id) is None:
        raise HTTPException(status_code=404, detail="mission not found")
    if not mission_control.cancel(mission_id):
        raise HTTPException(status_code=409, detail="This mission is not running")
    db.update_mission(mission_id, status="cancelled")
    emit(mission_id, "mission_cancelled", "Mission cancelled by the user", {})
    return {"cancelled": True}


@router.post("/missions/{mission_id}/confirm")
def confirm_action(mission_id: UUID, body: ConfirmBody) -> dict[str, bool]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    if not safety.resolve_confirm(mission_id, body.approved):
        raise HTTPException(status_code=409, detail="There is no pending confirmation")
    emit(
        mission_id,
        "ui_action" if body.approved else "waiting",
        "Action approved" if body.approved else "Action rejected",
        {"approved": body.approved},
    )
    return {"approved": body.approved}
