"""Poll the active window while a mission runs. Only a summary is stored."""

from __future__ import annotations

from threading import Event, Thread
from uuid import UUID

from app import db
from app.agent.events import emit
from app.agent.uia import snapshot
from app.agent.uia.chrome import list_tabs

_stops: dict[str, Event] = {}


def start(mission_id: UUID) -> None:
    key = str(mission_id)
    if key in _stops:
        return
    stop_event = Event()
    _stops[key] = stop_event
    Thread(target=_loop, args=(mission_id, stop_event), daemon=True).start()


def stop(mission_id: UUID) -> None:
    event = _stops.pop(str(mission_id), None)
    if event is not None:
        event.set()


def _summary(elements: list[dict[str, object]]) -> dict[str, object]:
    names = [str(element.get("name") or "") for element in elements if element.get("name")]
    interesting = [
        str(element["name"])
        for element in elements
        if element.get("control_type") in {"Button", "Edit", "Hyperlink", "TabItem", "Document"} and element.get("name")
    ]
    return {"element_count": len(elements), "key_elements": interesting[:8], "signature": "|".join(names[:12])}


def _loop(mission_id: UUID, stop_event: Event) -> None:
    previous = ""
    while not stop_event.is_set():
        try:
            window = snapshot.get_active_window()
            elements = snapshot.capture_tree(window)
            summary = _summary(elements)
            signature = str(summary.pop("signature"))
            if signature and signature != previous:
                previous = signature
                tabs = []
                try:
                    if str(window.get("process") or "").lower() == "chrome.exe":
                        tabs = [tab["name"] for tab in list_tabs()]
                except Exception:
                    tabs = []
                db.patch_world(
                    mission_id,
                    active_window={
                        "title": window.get("title"),
                        "process": window.get("process"),
                        "pid": window.get("pid"),
                    },
                    browser={
                        "open": bool(tabs) or str(window.get("process") or "").lower() == "chrome.exe",
                        "url": None,
                        "title": window.get("title"),
                        "tab": tabs[0] if tabs else None,
                        "tabs": tabs,
                        "active_tab": tabs[0] if tabs else window.get("title"),
                    },
                    ui_summary=summary,
                )
                emit(
                    mission_id,
                    "ui_observed",
                    f"Watching {window.get('title') or 'the desktop'}",
                    {"element_count": summary["element_count"]},
                )
        except Exception:
            pass
        stop_event.wait(1)
