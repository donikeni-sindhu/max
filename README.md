# REBORN

Desktop AI companion. Phase 1 is the monorepo scaffold: an Electron widget and a FastAPI backend that start together.

## Layout

- `widget/` — Electron + Vite + React + TypeScript
- `backend/` — FastAPI (`GET /health`)
- `supabase/` — migrations, `seed.sql`, and `config.toml`
- `.env.example` — environment variable names (no secrets)

## Prerequisites

- Node.js 20+
- Python 3.11+ (3.12 works)

## Setup

```powershell
Copy-Item .env.example .env
npm install --prefix widget
python -m venv backend/.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

On macOS/Linux, copy with `cp .env.example .env` and use `backend/.venv/bin/python`.

## Run

```bash
npm run dev
```

This starts:

- backend: `uvicorn app.main:app --reload` on `BACKEND_PORT` (default `8000`)
- widget: Electron window via `electron-vite`

## Test Phase 1

1. `npm run dev`
2. Open `http://127.0.0.1:8000/health` — response is `{"status":"ok"}`
3. The Electron window shows the same health status
4. Stop both with Ctrl+C in that terminal

If the widget exits immediately with `Electron uninstall`, the Electron binary was skipped during install. Download it once:

```powershell
node widget/node_modules/electron/install.js
```

## Test Phase 2

Requires the [Supabase CLI](https://supabase.com/docs/guides/local-development) and Docker.

```powershell
npx supabase start
npx supabase db reset
```

`db reset` applies `supabase/migrations` and `supabase/seed.sql`.

In Studio (`http://127.0.0.1:54323`), sign in is not required for the table editor when you use the local service role. Check:

- `missions` has one row, goal `I want to understand the paper 'Attention Is All You Need'`, status `learning`
- `concepts` has 7 rows for that mission, ordered from Sequence-to-Sequence through Multi-Head Attention + Positional Encoding
- `resources` has 5 selected links
- `world_state.state` contains `goal`, `browser`, `target_paper`, `pdf`, `current_knowledge`, `prerequisites`, and `resources`
- Realtime is on for `missions`, `world_state`, `concepts`, `agent_events`, and `character_state`

Demo login (local only): `demo@reborn.local` / `demo-password`. That user can read the mission. Another user cannot.

Widget types live in `widget/src/renderer/src/types/database.ts`. Backend models live in `backend/app/models.py`. The demo mission id is `22222222-2222-4222-8222-222222222222`.

## How REBORN sees the screen

REBORN reads the desktop through the Windows UI Automation tree (`pywinauto` backend `uia`), the same structured controls a screen reader uses. It does not take screenshots and it does not send the screen to a vision model.

A snapshot keeps useful controls only (buttons, edits, tabs, links, list items, menu items, documents, and named text), gives them short ids (`e1`, `e2`, ...), and stores a compact summary in `world_state`. The full tree stays in memory. The widget window is titled `REBORN Widget` and is left out of snapshots.

Actions (click, type, keys, scroll, tab selection) are allowed only for processes in `ALLOWED_APPS` (default `chrome.exe`, `msedge.exe`). Password fields are refused. Controls whose names include delete, uninstall, send, pay, purchase, or submit wait for `POST /missions/{id}/confirm`.

Chrome is launched with `--force-renderer-accessibility`. Its toolbar is visible to UIA; the PDF viewer and page body often are not. When the address bar is missing from the tree, REBORN still opens the URL in a dedicated Chrome profile, and it reads the paper by downloading the arXiv PDF and extracting text with `pypdf`. If UIA cannot drive a step, Playwright is the fallback, and `DEMO_MODE=true` replays the seeded path.

```powershell
backend\.venv\Scripts\python scripts\uia_dump.py
backend\.venv\Scripts\python scripts\uia_chrome_demo.py
```

`GET /debug/uia/snapshot` returns the compact tree of the active window.

## Run the companion

```powershell
npm run dev
```

Click the white character, enter a goal such as `I want to understand the paper 'Attention Is All You Need'`, then use **Start next concept**. Right-click the character for Pause, Demo mode, Replay, and Quit. `Ctrl+Shift+D` starts the demo goal.

Without Docker, the widget polls the backend. With Supabase running, it also subscribes to Realtime. Anonymous sign-in is enabled in `supabase/config.toml`.

See `DEMO_CHECKLIST.md` for the full demo pass.
