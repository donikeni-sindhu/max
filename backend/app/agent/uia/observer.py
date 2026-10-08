"""Observe the desktop slowly and persist only meaningful window or tab changes."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from uuid import UUID

from app import db
from app.agent.events import emit
from app.agent.uia import snapshot
from app.agent.uia.chrome import get_address_bar_url, list_tabs

_logger = logging.getLogger(__name__)


@dataclass
class ObserverTask:
    stop_event: threading.Event
    thread: threading.Thread


_stops: dict[str, ObserverTask] = {}
_stops_lock = threading.Lock()


def start(mission_id: UUID) -> None:
    key = str(mission_id)
    with _stops_lock:
        previous = _stops.get(key)
        if previous and previous.thread.is_alive():
            # A live observer is already serving this mission; reusing it avoids duplicate polling threads.
            return
        if previous:
            # Stale dictionary entries are removed so a dead thread cannot disable observation forever.
            previous.stop_event.set()
            _stops.pop(key, None)
        stop_event = threading.Event()
        thread = threading.Thread(target=_loop, args=(mission_id, stop_event), daemon=True)
        _stops[key] = ObserverTask(stop_event, thread)
        thread.start()


def stop(mission_id: UUID) -> None:
    with _stops_lock:
        task = _stops.pop(str(mission_id), None)
    if task is not None:
        task.stop_event.set()
        # Join briefly so a completed mission does not leave a stale observer behind.
        task.thread.join(timeout=2)


def _summary(observed: snapshot.Snapshot) -> dict[str, object]:
    names = [str(element.get("name") or "") for element in observed.elements if element.get("name")]
    interesting = [
        str(element["name"])
        for element in observed.elements
        if element.get("control_type") in {"Button", "Edit", "Hyperlink", "TabItem", "Document"} and element.get("name")
    ]
    return {"element_count": len(observed.elements), "key_elements": interesting[:8], "signature": "|".join(names[:12])}


def _loop(mission_id: UUID, stop_event: threading.Event) -> None:
    """Observe on a COM-initialized thread, skipping busy UIA ticks and backing off repeated provider errors."""

    previous: tuple[str, str, tuple[str, ...]] | None = None
    interval = 4.0
    last_error = ""
    while not stop_event.is_set():
        if not snapshot.UIA_LOCK.acquire(blocking=False):
            # A click or keyboard action owns the provider; skipping is safer than queuing a stale tree walk.
            stop_event.wait(interval)
            continue
        try:
            with snapshot.com_initialized():
                # The extra lock scope protects window identity and the following UIA capture as one observation.
                window = snapshot.get_active_window()
                observed = snapshot.capture_tree(window)
            summary = _summary(observed)
            summary.pop("signature", None)
            tabs: list[str] = []
            if str(window.get("process") or "").lower() == "chrome.exe":
                tabs = [tab["name"] for tab in list_tabs()]
            signature = (str(window.get("title") or ""), str(window.get("process") or ""), tuple(tabs))
            if signature != previous:
                previous = signature
                current_url = get_address_bar_url() if tabs else None
                db.patch_world(
                    mission_id,
                    active_window={
                        "title": window.get("title"),
                        "process": window.get("process"),
                        "pid": window.get("pid"),
                    },
                    browser={
                        "open": bool(tabs) or signature[1].lower() == "chrome.exe",
                        "url": current_url,
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
                    {"element_count": summary["element_count"], "tabs": tabs},
                )
            last_error = ""
            interval = 4.0
        except Exception as exc:
            # Log each distinct provider failure once and back off so a broken UIA provider cannot flood logs.
            error_key = f"{type(exc).__name__}: {exc}"
            if error_key != last_error:
                _logger.warning("Observer snapshot failed for mission %s: %s", mission_id, error_key)
                last_error = error_key
            interval = min(20.0, max(5.0, interval * 2))
        finally:
            snapshot.UIA_LOCK.release()
        stop_event.wait(interval)
