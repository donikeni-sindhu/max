"""Playwright fallback when UIA cannot drive the browser. One shared context."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

_playwright: Any = None
_browser: Any = None
_context: Any = None


def _page() -> Any:
    global _playwright, _browser, _context
    if _context is not None:
        return _context.new_page()
    from playwright.sync_api import sync_playwright

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=False)
    _context = _browser.new_context()
    return _context.new_page()


def search(query: str) -> dict[str, Any]:
    try:
        page = _page()
        page.goto(f"https://duckduckgo.com/?q={quote_plus(query)}", timeout=15000, wait_until="domcontentloaded")
        links = page.locator("a[data-testid='result-title-a']")
        count = min(links.count(), 5)
        results = []
        for index in range(count):
            item = links.nth(index)
            results.append({"title": item.inner_text(), "url": item.get_attribute("href") or ""})
        return {"ok": True, "detail": f"{len(results)} playwright results", "results": results}
    except Exception as exc:
        return {"ok": False, "detail": str(exc), "results": []}


def open_url(url: str) -> dict[str, Any]:
    try:
        page = _page()
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        return {"ok": True, "detail": f"Opened {url}", "title": page.title()}
    except Exception as exc:
        return {"ok": False, "detail": str(exc), "url": url}
