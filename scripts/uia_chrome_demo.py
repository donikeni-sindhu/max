"""Launch Chrome, search for the paper, open the arXiv PDF, then refocus it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agent.uia import chrome

launched = chrome.launch_chrome("https://duckduckgo.com")
print("launch", launched)
found = chrome.search("Attention Is All You Need research paper")
print("search", found.get("detail"), len(found.get("results") or []))
paper = chrome.open_paper_pdf("Attention Is All You Need")
print("paper", paper)
second = chrome.open_resource("https://jalammar.github.io/illustrated-transformer/", "Illustrated Transformer")
print("second", second.get("detail"))
focused = chrome.focus_tab(paper.get("tab") or "1706")
print("refocus", focused)
