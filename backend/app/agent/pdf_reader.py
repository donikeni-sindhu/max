"""Download an arXiv PDF and pull out title, abstract, headings, and references."""

from __future__ import annotations

import io
import re

import httpx

from app.agent.demo_data import PAPER_EXCERPT


def extract_pdf(url: str) -> dict[str, str]:
    try:
        response = httpx.get(url, timeout=20, follow_redirects=True)
        response.raise_for_status()
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(response.content))
        pages = []
        for page in reader.pages[:4]:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)
        title = _first_line(text)
        abstract = _section(text, "abstract")
        headings = _headings(text)
        references = _section(text, "references")
        excerpt = "\n".join(
            part for part in [title, abstract[:800], headings[:800], references[:400]] if part
        )
        return {"title": title, "excerpt": excerpt[:2000] or PAPER_EXCERPT, "url": url}
    except Exception:
        return {"title": "", "excerpt": PAPER_EXCERPT, "url": url}


def _first_line(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if len(clean) > 8:
            return clean[:180]
    return ""


def _section(text: str, name: str) -> str:
    match = re.search(rf"{name}(.{{0,1200}})", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(0).strip() if match else ""


def _headings(text: str) -> str:
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if re.match(r"^\d+(\.\d+)*\s+\S+", clean) and len(clean) < 80:
            lines.append(clean)
    return "\n".join(lines[:12])
