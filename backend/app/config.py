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
    anthropic_api_key: str = ""
    demo_mode: bool = True
    backend_port: int = 8000
    allowed_apps: str = "chrome.exe,msedge.exe"
    anthropic_model: str = "claude-sonnet-4-6"

    def allowed_app_names(self) -> list[str]:
        return [part.strip().lower() for part in self.allowed_apps.split(",") if part.strip()]


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
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        demo_mode=_bool(os.getenv("DEMO_MODE"), True),
        backend_port=int(os.getenv("BACKEND_PORT") or "8000"),
        allowed_apps=os.getenv("ALLOWED_APPS") or "chrome.exe,msedge.exe",
        anthropic_model=os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-6",
    )
