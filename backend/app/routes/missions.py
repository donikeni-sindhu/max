from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app import db
from app.agent import orchestrator
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
    background.add_task(orchestrator.run, mission_id, goal)
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
    return orchestrator.advance(mission_id)


@router.post("/missions/{mission_id}/replay")
def replay_mission(mission_id: UUID, background: BackgroundTasks) -> dict[str, str]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    goal = str(bundle["mission"]["goal"])
    background.add_task(orchestrator.run, mission_id, goal)
    return {"id": str(mission_id), "status": "replay"}


@router.post("/missions/{mission_id}/confirm")
def confirm_action(mission_id: UUID, body: ConfirmBody) -> dict[str, bool]:
    bundle = db.get_bundle(mission_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="mission not found")
    safety.resolve_confirm(mission_id, body.approved)
    emit(
        mission_id,
        "ui_action" if body.approved else "waiting",
        "Action approved" if body.approved else "Action rejected",
        {"approved": body.approved},
    )
    return {"approved": body.approved}
