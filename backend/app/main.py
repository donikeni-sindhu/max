import hmac
import os
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings
from app.routes.commands import router as commands_router
from app.routes.missions import router as missions_router
from app.routes.permissions import router as permissions_router
from app.agent.uia import snapshot

app = FastAPI(title="REBORN", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    # The widget has fixed local origins; the null origin is needed by packaged file:// builds,
    # where the random launch token below supplies the request-level check CORS cannot provide.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type", "x-reborn-token"],
)


@app.on_event("startup")
def initialize_desktop_context() -> None:
    """Set DPI before the first control lookup and remember the pre-widget foreground window."""

    snapshot.initialize_dpi_awareness()
    # The Electron widget may take focus immediately after launch; this captures the user's prior target first.
    snapshot.get_active_window()


@app.middleware("http")
async def require_launch_token(request: Request, call_next):
    # Bind every local API call to the current launcher session so another local page cannot
    # issue browser-control commands merely because the backend listens on loopback.
    if request.method != "OPTIONS":
        expected = os.getenv("REBORN_TOKEN", "")
        supplied = request.headers.get("x-reborn-token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=403, content={"detail": "Invalid REBORN launch token"})
    return await call_next(request)
app.include_router(missions_router)
app.include_router(commands_router)
app.include_router(permissions_router)
if get_settings().debug_routes:
    # UIA debug endpoints can trigger real desktop input, so they are opt-in for local diagnosis.
    from app.routes.debug import router as debug_router

    app.include_router(debug_router)


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
