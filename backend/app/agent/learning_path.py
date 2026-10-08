from uuid import UUID

from app import db
from app.agent.events import emit
from app.models import MissionSummary, WorldStateData


def publish_path(mission_id: UUID, goal: str, target_title: str, pdf_url: str, excerpt: str, names: list[str]) -> None:
    emit(mission_id, "path_ready", "Assembling the learning path", {"goal": goal})
    bundle = db.get_bundle(mission_id) or {}
    resources = [
        {
            "title": row["title"],
            "url": row["url"],
            "source": row.get("source"),
            "score": row.get("score"),
            "selected": row.get("selected", False),
        }
        for row in bundle.get("resources", [])
    ]
    state = WorldStateData(
        goal=goal,
        target_paper={"title": target_title, "url": pdf_url.replace("/pdf/", "/abs/") if pdf_url else None},
        pdf={"url": pdf_url, "title": target_title, "text_excerpt": excerpt[:500]},
        current_knowledge="",
        prerequisites=names,
        resources=resources,
        summary=MissionSummary(concepts_identified=len(names), resources_explored=len(resources)),
    )
    db.save_world(mission_id, state.model_dump(mode="json"))
    db.update_mission(mission_id, status="learning", target_title=target_title)
    emit(mission_id, "path_ready", f"Learning path is ready for {target_title}", {"concepts": len(names)})
