"""Expose session app-interaction approvals so the user can review and revoke them in the widget."""

from fastapi import APIRouter

from app.agent.uia.safety import approved_apps, revoke_app_approval

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/apps")
def list_app_approvals() -> dict[str, list[str]]:
    """Return only temporary non-browser app grants for the current backend session."""

    return {"apps": approved_apps()}


@router.delete("/apps/{app_name}")
def delete_app_approval(app_name: str) -> dict[str, bool]:
    """Revoke a friendly app-name grant immediately without changing the configured browser defaults."""

    return {"revoked": revoke_app_approval(app_name)}
