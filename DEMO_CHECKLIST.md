# REBORN demo checklist

1. Copy `.env.example` to `.env`.
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` when Supabase is running
   - `ANTHROPIC_API_KEY` for live concept extraction (optional; the seeded path is used without it)
   - `DEMO_MODE=true`
   - `BACKEND_PORT=8000`
   - `ALLOWED_APPS=chrome.exe,msedge.exe`
2. Install widget and backend dependencies, including `pywinauto`, `comtypes`, `pywin32`, `psutil`, and `pypdf`.
3. Start Supabase when you want Realtime: `npx supabase start` then `npx supabase db reset`. Docker Desktop is required. The widget still runs by polling the backend if Supabase is down.
4. Confirm Google Chrome is installed. REBORN launches it with `--force-renderer-accessibility` and a profile under `%LOCALAPPDATA%\REBORN\chrome-profile`.
5. From the repo root, print the active window tree:

   ```powershell
   backend\.venv\Scripts\python scripts\uia_dump.py
   ```

6. Drive Chrome through the paper demo:

   ```powershell
   backend\.venv\Scripts\python scripts\uia_chrome_demo.py
   ```

   Expect a Chrome window, a search for the paper, the arXiv PDF, a second tab for The Illustrated Transformer, then focus back on the paper tab. If the page tree is empty, the script still opens the PDF URL directly.
7. `npm run dev`.
8. What to do at each step:
   - Click the white character. Ask: `I want to understand the paper 'Attention Is All You Need'`.
   - The character should perk up, then celebrate when the path is ready. The panel lists 7 concepts with arrows.
   - Open **World state** and confirm `active_window` and `ui_summary` are present.
   - Click **Start next concept**. Chrome opens that concept's resource and the speech bubble types a short explanation.
   - Repeat until the **Research Mission Complete** card appears. The original PDF tab is focused again.
   - Right-click for Pause, Demo mode, Replay, or Quit.
   - Press `Ctrl+Shift+D` to run the demo goal again.
   - Open **Debug** for the latest `agent_events` and UIA summary.
9. A pending sensitive click shows Approve / Reject and calls `POST /missions/{id}/confirm`.
