from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.commands import parse_open_command
from app.agent.uia import chrome
from app.config import get_settings

router = APIRouter(tags=["commands"])


class CommandRequest(BaseModel):
    command: str


@router.post("/commands")
def execute_command(body: CommandRequest) -> dict[str, object]:
    # Unrecognized text returns to the existing mission route instead of guessing that it is navigation.
    url = parse_open_command(body.command)
    if url is None:
        return {"handled": False}

    # The normal UIA-controlled Chrome path keeps navigation inside the configured desktop profile.
    result = chrome.open_url(url)
    # Playwright's synchronous browser is thread-bound, so its optional fallback remains disabled by default.
    if not result.get("ok") and get_settings().playwright_fallback:
        from app.agent.fallback import browser as playwright_browser

        result = playwright_browser.open_url(url)
    if not result.get("ok"):
        detail = str(result.get("detail") or "Could not open the requested website")
        raise HTTPException(status_code=502, detail=detail)
    return {"handled": True, "url": url, "message": f"Opened {urlsplit(url).hostname or url}"}
