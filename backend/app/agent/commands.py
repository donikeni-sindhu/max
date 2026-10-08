"""Recognize simple, explicit browser navigation commands."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


# Require an explicit navigation verb so a learning topic such as "YouTube recommendations" is not opened as a site.
_OPEN_VERB = re.compile(r"^(?:please\s+)?(?:open|visit|go to|navigate to)\s+(.+?)\s*[.!?]*$", re.IGNORECASE)
# These common site names omit the TLD in ordinary speech; explicit domains still work below.
_KNOWN_SITES = {
    "youtube": "https://www.youtube.com/",
    "youtube.com": "https://www.youtube.com/",
    "www.youtube.com": "https://www.youtube.com/",
    "youtu.be": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "google.com": "https://www.google.com/",
    "gmail": "https://mail.google.com/",
    "gmail.com": "https://mail.google.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "wikipedia.org": "https://www.wikipedia.org/",
    "github": "https://github.com/",
    "github.com": "https://github.com/",
}
_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::\d{1,5})?(?:/[^\s]*)?$", re.IGNORECASE)


def parse_open_command(command: str) -> str | None:
    """Return a safe HTTP(S) URL for explicit open/visit/go-to commands."""
    match = _OPEN_VERB.fullmatch(command.strip())
    if not match:
        return None

    destination = match.group(1).strip().rstrip(".!?,;").strip()
    if not destination:
        return None

    known = _KNOWN_SITES.get(destination.lower())
    if known:
        return known

    if not re.match(r"^https?://", destination, re.IGNORECASE):
        if not _DOMAIN.fullmatch(destination) or "." not in destination.split("/", 1)[0]:
            return None
        destination = f"https://{destination}"

    parsed = urlsplit(destination)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return destination
