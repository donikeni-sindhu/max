"""Small, data-driven hints for popular apps; unknown apps still use the generic launch routes."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AppSpec:
    """Describe app-specific names while keeping launch behavior in the generic launcher."""

    name: str
    aliases: tuple[str, ...] = ()
    protocol: str | None = None
    web_url: str | None = None
    process_names: tuple[str, ...] = ()
    window_titles: tuple[str, ...] = ()
    package_names: tuple[str, ...] = ()
    messaging: bool = False


# Registry entries contain matching hints only, so every app follows the same strategy ladder.
APP_REGISTRY: tuple[AppSpec, ...] = (
    AppSpec("WhatsApp", ("whats app",), "whatsapp", "https://web.whatsapp.com/", ("whatsapp.exe", "whatsapproot.exe"), ("whatsapp",), ("5319275a.WhatsAppDesktop",), True),
    AppSpec("Microsoft Teams", ("teams",), "msteams", "https://teams.microsoft.com/", ("ms-teams.exe", "teams.exe"), ("microsoft teams",), ("MSTeams_8wekyb3d8bbwe",), True),
    AppSpec("Slack", (), "slack", "https://app.slack.com/", ("slack.exe",), ("slack",), (), True),
    AppSpec("Telegram", ("telegram desktop",), "tg", "https://web.telegram.org/", ("telegram.exe",), ("telegram",), (), True),
    AppSpec("Signal", ("signal desktop",), "sgnl", None, ("signal.exe",), ("signal",), (), True),
    AppSpec("Spotify", (), "spotify", "https://open.spotify.com/", ("spotify.exe",), ("spotify",)),
    AppSpec("Notepad", ("windows notepad",), None, None, ("notepad.exe",), ("notepad",)),
    AppSpec("Calculator", ("calc", "windows calculator"), None, None, ("calculator.exe", "calc.exe"), ("calculator",), ("Microsoft.WindowsCalculator",)),
    AppSpec("Google Chrome", ("chrome",), None, None, ("chrome.exe",), ("chrome",)),
    AppSpec("Microsoft Edge", ("edge",), "microsoft-edge", None, ("msedge.exe",), ("edge",)),
)


def normalize_name(value: str) -> str:
    """Normalize punctuation and whitespace so aliases compare without app-specific code."""

    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def lookup(name: str) -> AppSpec | None:
    """Return a registry hint only for an exact normalized name or alias."""

    wanted = normalize_name(name)
    return next(
        (spec for spec in APP_REGISTRY if wanted in {normalize_name(spec.name), *(normalize_name(alias) for alias in spec.aliases)}),
        None,
    )


def identify(name: str = "", process: str = "", title: str = "", package: str = "") -> AppSpec | None:
    """Resolve a known app from process, package, or title metadata for policy and verification."""

    values = {normalize_name(value) for value in (name, process, title, package) if value}
    for spec in APP_REGISTRY:
        hints = {normalize_name(spec.name), *(normalize_name(alias) for alias in spec.aliases)}
        hints.update(normalize_name(item.removesuffix(".exe")) for item in spec.process_names)
        hints.update(normalize_name(item) for item in spec.window_titles)
        hints.update(normalize_name(item) for item in spec.package_names)
        if any(value and any(hint in value or value in hint for hint in hints) for value in values):
            return spec
    return None


def is_messaging_app(process: str = "", title: str = "", package: str = "") -> bool:
    """Flag apps whose Enter key can send a message, using registry metadata rather than hardcoding flow logic."""

    spec = identify(process=process, title=title, package=package)
    return bool(spec and spec.messaging)
