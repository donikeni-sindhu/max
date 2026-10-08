# REBORN

Desktop AI companion. Phase 1 is the monorepo scaffold: an Electron widget and a FastAPI backend that start together.

## Layout

- `widget/` — Electron + Vite + React + TypeScript
- `backend/` — FastAPI (`GET /health`)
- `supabase/` — migrations, `seed.sql`, and `config.toml`
- `.env.example` — environment variable names (no secrets)

## Prerequisites

- Node.js 20+
- Windows 10 or 11 for desktop control, Node.js 20+, and Python 3.11+ (3.12 works)

## Setup

```powershell
Copy-Item .env.example .env
npm install --prefix widget
python -m venv backend/.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

Add your Groq key to `GROQ_API_KEY` in the ignored `.env` file. REBORN uses `openai/gpt-oss-120b` by default; set `GROQ_MODEL` there to choose another supported Groq model.

The research and chat backend can run on macOS/Linux, but desktop app launching and UI Automation are Windows-only features.

## Run

```bash
npm run dev
```

This starts:

- backend: `uvicorn app.main:app --reload` on `BACKEND_PORT` (default `8000`)
- widget: Electron window via `electron-vite`

## Test Phase 1

1. `npm run dev`
2. The launcher creates a private per-run token and the widget uses it for backend calls.
3. Stop both with Ctrl+C in that terminal

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

Actions (click, type, keys, scroll, tab selection) are allowed by default only for processes in `INTERACT_ALLOWED_APPS` (default `chrome.exe`, `msedge.exe`). REBORN asks before first-time interaction with another app and remembers that app approval for the backend session; approvals can be revoked in the widget menu. Password and payment-code fields are refused. Sensitive actions and message sending require confirmation. Confirmation uses whole words, so labels such as “Payment history” and “Resend” do not trigger the sensitive-action prompt. The optional synchronous Playwright URL fallback is disabled by default (`PLAYWRIGHT_FALLBACK=false`) because Playwright's sync browser must stay on one worker thread; REBORN uses its dedicated Chrome profile instead.

Chrome is launched with `--force-renderer-accessibility`. Its toolbar is visible to UIA; the PDF viewer and page body often are not. When the address bar is missing from the tree, REBORN opens the URL in a dedicated Chrome profile, and it reads the paper by downloading the arXiv PDF and extracting text with `pypdf`. UIA failures are reported to the mission panel instead of silently replaying canned results. `DEMO_MODE=true` enables the explicit demo fallback for the seeded paper goal.

```powershell
backend\.venv\Scripts\python scripts\uia_dump.py
backend\.venv\Scripts\python scripts\uia_chrome_demo.py
```

`GET /debug/uia/snapshot` is disabled by default. Set `DEBUG_ROUTES=true` for local diagnosis; the endpoint still requires the current launch token.

## Run the companion

```powershell
npm run dev
```

Click the white character and enter a command such as `Open YouTube`, or a learning goal such as `I want to understand the paper 'Attention Is All You Need'`. Right-click the character for Pause, Demo mode, Replay, and Quit. Use the **×** button in the top-right corner to close REBORN. `Ctrl+Shift+D` starts the demo goal.

Without Docker, the widget polls the backend. With Supabase running, it also subscribes to Realtime. Anonymous sign-in is enabled in `supabase/config.toml`.

See `DEMO_CHECKLIST.md` for the full demo pass.
