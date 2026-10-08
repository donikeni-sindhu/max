"""Chrome control through the UIA tree."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any
from urllib.parse import quote_plus, urlsplit
from xml.etree import ElementTree

import httpx

from app.agent.demo_data import PAPER_PDF
from app.agent import mission_control
from app.agent.uia import actions, snapshot

_paper_tab = ""
_opened: list[dict[str, str]] = []


def paper_tab_name() -> str:
    return _paper_tab


def chrome_path() -> str:
    roots = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    for root in roots:
        candidate = os.path.join(root, "Google", "Chrome", "Application", "chrome.exe")
        if root and os.path.exists(candidate):
            return candidate
    return ""


def _chrome_hwnd() -> int:
    import psutil
    import win32gui
    import win32process

    preferred: list[int] = []
    fallback: list[int] = []

    def visit(handle: int, _: object) -> None:
        # A cloaked Chrome window may pass IsWindowVisible but cannot receive input on the current desktop.
        if not snapshot.is_window_visible(handle):
            return
        title = win32gui.GetWindowText(handle)
        if not title or "reborn" in title.lower():
            return
        _, pid = win32process.GetWindowThreadProcessId(handle)
        try:
            process = psutil.Process(pid)
            if process.name().lower() != "chrome.exe":
                return
            chain = [process, *process.parents()]
            command = " ".join(" ".join(item.cmdline()) for item in chain)
        except Exception:
            return
        if "chrome-profile" in command:
            preferred.append(handle)

    win32gui.EnumWindows(visit, None)
    return preferred[0] if preferred else 0


def _chrome_window() -> dict[str, Any]:
    hwnd = _chrome_hwnd()
    if not hwnd:
        return {"title": "", "process": "chrome.exe", "pid": 0, "hwnd": 0, "rect": [0, 0, 0, 0]}
    import psutil
    import win32gui
    import win32process

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        process = psutil.Process(pid).name()
    except Exception:
        process = "chrome.exe"
    return {
        "title": win32gui.GetWindowText(hwnd),
        "process": process,
        "pid": pid,
        "hwnd": hwnd,
        "rect": list(win32gui.GetWindowRect(hwnd)),
    }


def profile_dir() -> str:
    root = os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()), "REBORN", "chrome-profile")
    os.makedirs(root, exist_ok=True)
    return root


def launch_chrome(url: str | None = None, mission_id: Any = None) -> dict[str, Any]:
    """Start the dedicated Chrome profile and report success only when its window is visible."""

    # Check cancellation immediately before process launch because this is an irreversible browser side effect.
    if mission_id is not None and mission_control.is_cancelled(mission_id):
        return {"ok": False, "detail": "Mission was cancelled", "url": url}
    if url:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return {"ok": False, "detail": "Only HTTP and HTTPS URLs can be opened", "url": url}
    path = chrome_path()
    if not path:
        return {"ok": False, "detail": "Chrome is not installed"}
    command = [
        path,
        "--force-renderer-accessibility",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir()}",
    ]
    if url:
        command.append(url)
    try:
        before = str(_chrome_window().get("title") or "")
        subprocess.Popen(command)
        title = _wait_title(before) if url else before
        if url and title is None:
            window = _chrome_window()
            detail = (
                f"Chrome did not create a visible window for {url}"
                if not window.get("hwnd")
                else f"Timed out waiting for {url} to load"
            )
            return {"ok": False, "detail": detail, "url": url}
        if url:
            _remember(title, url)
        time.sleep(0.4)
        window = _chrome_window()
        if not window.get("hwnd"):
            return {"ok": False, "detail": "Chrome did not create a visible window", "url": url}
        evidence = {key: window.get(key) for key in ("title", "process", "hwnd")}
        return {"ok": True, "detail": "Launched Chrome", "url": url, "tab": title, "evidence": evidence}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def _remember(name: str, url: str) -> None:
    _opened.append({"name": name, "url": url})


def _wait_title(previous: str) -> str | None:
    deadline = time.monotonic() + 8
    title = previous
    while time.monotonic() < deadline:
        title = str(_chrome_window().get("title") or "")
        if title and title != previous and "New Tab" not in title:
            return title
        time.sleep(0.4)
    # A timeout is a failed navigation, not evidence that a page is ready for the next action.
    return None


def list_tabs() -> list[dict[str, str]]:
    observed = snapshot.capture_tree(_chrome_window())
    visible = [
        {"name": element["name"], "id": element["id"]}
        for element in observed.elements
        if element["control_type"] == "TabItem" and element["name"]
    ]
    if visible:
        return visible
    return [{"name": tab["name"], "id": tab["url"]} for tab in _opened]


def get_address_bar_url() -> str:
    observed = snapshot.capture_tree(_chrome_window())
    for element in observed.elements:
        if element["control_type"] == "Edit" and "address" in element["name"].lower():
            return str(element.get("value") or "")
    return ""


def focus_tab(name: str, mission_id: Any = None) -> dict[str, Any]:
    window = _chrome_window()
    if not window["hwnd"]:
        return {"ok": False, "detail": "Chrome is not open"}
    focused = actions.focus_hwnd(int(window["hwnd"]), mission_id)
    if not focused["ok"]:
        return focused
    observed = snapshot.capture_tree(window)
    match = next(
        (
            element
            for element in observed.elements
            if element["control_type"] == "TabItem" and name.lower() in element["name"].lower()
        ),
        None,
    )
    if match is not None:
        return actions.click(match["id"], mission_id, str(match["name"]), observed)
    wanted = name.lower()
    for _ in range(12):
        current = str(_chrome_window().get("title") or "")
        if wanted in current.lower() or current.lower() in wanted:
            return {"ok": True, "detail": f"Focused {current}"}
        actions.press_keys("^{TAB}", mission_id=mission_id, process_name="chrome.exe", observed=observed)
        time.sleep(0.35)
    return {"ok": False, "detail": f"Tab not found: {name}"}


def open_url(url: str, mission_id: Any = None) -> dict[str, Any]:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return {"ok": False, "detail": "Only HTTP and HTTPS URLs can be opened", "url": url}
    # Reserve each destination before touching Chrome so repeat steps and concurrent workers cannot reopen it.
    allowed, detail = mission_control.reserve_url(mission_id, url)
    if not allowed:
        return {"ok": False, "detail": detail, "url": url, "skipped": "already opened" in detail}
    previous = str(_chrome_window().get("title") or "")
    window = _chrome_window()
    opened_by_keys = False
    if window["hwnd"] and actions.focus_hwnd(int(window["hwnd"]), mission_id)["ok"]:
        before_action = snapshot.capture_tree(_chrome_window())
        pressed = actions.press_keys("^l", mission_id=mission_id, process_name="chrome.exe", observed=before_action)
        observed = snapshot.capture_tree(_chrome_window()) if pressed["ok"] else None
        address = next(
            (
                element
                for element in (observed.elements if observed else ())
                if element["control_type"] == "Edit" and "address" in element["name"].lower()
            ),
            None,
        )
        if address:
            typed = actions.type_text(
                address["id"], url, human_delay=True, mission_id=mission_id,
                expected_name=str(address["name"]), observed=observed,
            )
            if typed["ok"]:
                submitted = actions.press_keys(
                    "{ENTER}", mission_id=mission_id, process_name="chrome.exe", observed=observed,
                )
                opened_by_keys = bool(submitted["ok"])
    if not opened_by_keys:
        # Launching a new Chrome process is the single fallback route; do not retry this URL in another browser.
        return launch_chrome(url, mission_id)
    title = _wait_title(previous)
    if title is None:
        return {"ok": False, "detail": f"Timed out waiting for {url} to load", "url": url}
    if _opened:
        _opened[-1] = {"name": title or url, "url": url}
    else:
        _remember(title or url, url)
    return {"ok": True, "detail": f"Opened {url}", "tab": title, "url": url}


def search(query: str, mission_id: Any = None) -> dict[str, Any]:
    url = f"https://duckduckgo.com/?q={quote_plus(query)}"
    opened = open_url(url, mission_id)
    if not opened["ok"]:
        return {**opened, "results": []}
    time.sleep(1.5)
    observed = snapshot.capture_tree(_chrome_window())
    results: list[dict[str, str]] = []
    for element in observed.elements:
        if element["control_type"] != "Hyperlink":
            continue
        name = element["name"].strip()
        if len(name) < 8:
            continue
        link = str(element.get("value") or "")
        if link.startswith("http"):
            results.append({"title": name, "url": link})
        if len(results) == 5:
            break
    if not results:
        results = _search_html(query)
    return {"ok": True, "detail": f"{len(results)} results", "results": results, "query": query}


def _search_html(query: str) -> list[dict[str, str]]:
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "REBORN"},
        )
        response.raise_for_status()
    except Exception:
        return []
    results: list[dict[str, str]] = []
    for line in response.text.split("<a "):
        if "result__a" not in line:
            continue
        href = _attr(line, "href")
        title = _text(line)
        if href.startswith("http") and title:
            results.append({"title": title, "url": href})
        if len(results) == 5:
            break
    return results


def _attr(tag: str, name: str) -> str:
    marker = f'{name}="'
    start = tag.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = tag.find('"', start)
    return tag[start:end]


def _text(tag: str) -> str:
    start = tag.find(">")
    end = tag.find("<", start + 1)
    if start < 0 or end < 0:
        return ""
    return tag[start + 1 : end].strip()


def _arxiv_pdf_url(title: str) -> str:
    if "attention is all you need" in title.lower():
        return PAPER_PDF
    try:
        response = httpx.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": f'ti:"{title}"', "max_results": 1},
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        for entry_id in root.findall("{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}id"):
            if entry_id.text and "arxiv.org" in entry_id.text:
                return entry_id.text.replace("/abs/", "/pdf/")
    except Exception:
        return ""
    return ""


def open_paper_pdf(title: str, mission_id: Any = None) -> dict[str, Any]:
    global _paper_tab
    # Resolve the paper URL first so one mission does not open both a search page and its PDF.
    pdf_url = _arxiv_pdf_url(title)
    if not pdf_url:
        return {"ok": False, "detail": f"Could not find an arXiv PDF for {title}", "title": title}
    opened = open_url(pdf_url, mission_id)
    if not opened.get("ok"):
        return {**opened, "title": title, "url": pdf_url}
    _paper_tab = str(opened.get("tab") or title)
    return {"ok": True, "detail": f"Paper tab {_paper_tab}", "url": pdf_url, "tab": _paper_tab, "title": title}


def open_resource(url: str, name: str, mission_id: Any = None) -> dict[str, Any]:
    opened = open_url(url, mission_id)
    if opened.get("ok") and _opened:
        _opened[-1]["name"] = name
    return {**opened, "name": name}
