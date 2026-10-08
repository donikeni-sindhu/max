import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agent.uia.snapshot import capture_tree, compact_for_llm, get_active_window

window = get_active_window()
print(f"window: {window.get('title')} ({window.get('process')})")
print(compact_for_llm(capture_tree(window)) or "(no elements)")
