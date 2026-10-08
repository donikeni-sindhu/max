from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")


class Settings(BaseModel):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    groq_api_key: str = ""
    # Canned output is opt-in so real failures stay visible during ordinary use.
    demo_mode: bool = False
    backend_port: int = 8000
    interact_allowed_apps: str = "chrome.exe,msedge.exe"
    groq_model: str = "openai/gpt-oss-120b"
    # Domain suffixes keep resource ranking away from video sites unless asked.
    blocked_domains: str = "youtube.com,youtu.be,m.youtube.com"
    max_actions_per_mission: int = 25
    launch_verify_timeout: float = 10.0
    playwright_fallback: bool = False
    debug_routes: bool = False

    def interact_allowed_app_names(self) -> list[str]:
        """Return the processes that can be interacted with without a session-specific approval."""

        return [part.strip().lower() for part in self.interact_allowed_apps.split(",") if part.strip()]


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    import os

    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        demo_mode=_bool(os.getenv("DEMO_MODE"), False),
        backend_port=int(os.getenv("BACKEND_PORT") or "8000"),
        interact_allowed_apps=os.getenv("INTERACT_ALLOWED_APPS") or "chrome.exe,msedge.exe",
        groq_model=os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b",
        blocked_domains=os.getenv("BLOCKED_DOMAINS") or "youtube.com,youtu.be,m.youtube.com",
        max_actions_per_mission=int(os.getenv("MAX_ACTIONS_PER_MISSION") or "25"),
        launch_verify_timeout=float(os.getenv("LAUNCH_VERIFY_TIMEOUT") or "10"),
        playwright_fallback=_bool(os.getenv("PLAYWRIGHT_FALLBACK"), False),
        debug_routes=_bool(os.getenv("DEBUG_ROUTES"), False),
    )
