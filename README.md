# [Meeting]32 — "Meeting → Done" Ops Copilot

A chatbot that turns messy meeting notes into **tracked action items, follow-up email drafts, and
calendar events** — with a live **Action Board** the agent drives straight from the chat. Built for
SMB owners and heads of department who don't want another tool to babysit: paste the notes, and the
work gets organized, assigned, and scheduled.

> M32 Fullstack + AI take-home. The name is a play on **M32** → **[Meeting]32**.

<!-- 📹 Demo video: <link to be added> -->

## What it does

- **Extract** — paste notes / a transcript (or attach a `.txt`/`.md`/`.pdf`/screenshot) and the
  agent pulls out concrete action items with owners and due dates.
- **Assign to your team** — when your workspace has members, owners are matched to real teammates
  (canonical name on the board, real email on follow-ups).
- **Live Action Board** — items appear, update, and change status in real time as the agent works.
- **Follow-up email** — drafts a warm, plain-language recap and sends it via Gmail to the owners.
- **Calendar** — proposes events (flagging conflicts with your existing agenda), creates them, and
  can **reschedule, rename, or remove** events it created.
- **Approve / Decline buttons** — anything with an external side effect (send email, create /
  move / cancel events) shows inline action buttons; no need to type "yes".
- **Workspaces** — shared org board, member invites, multi-session history with auto-titles.

## Stack

| Layer | Tech |
| --- | --- |
| **Frontend** | React 19 + Vite + TypeScript, Tailwind v4, shadcn (Base UI), Vercel AI Elements, **bun** |
| **Backend** | Python 3.12, FastAPI, **LangGraph** multi-agent, SQLAlchemy 2 + Alembic, managed with **uv** |
| **Database** | Neon (Postgres) |
| **LLM** | Gemini (free tier) behind a provider wrapper — one-line swap to OpenAI |
| **Integrations** | Composio (Gmail + Google Calendar), Google OAuth |
| **Hosting** | Vercel (frontend) · Render (backend) · Neon (DB) |

### How the agent works

A LangGraph router classifies each turn and dispatches to a specialized node:

```
            ┌─ extract ─▶ extractor ─▶ summarize
            ├─ edit ────▶ edit (board add/update/delete)
router ─────┼─ comms ───▶ comms (draft email · plan / reschedule / cancel events)
            ├─ confirm ─▶ confirm (the only place external side effects happen)
            └─ chat ────▶ respond
```

Extraction and edits are **deterministic-after-LLM** (the LLM returns structured output; we apply
DB writes ourselves), which is far more reliable than a free-form tool-calling loop. External calls
(Gmail / Calendar) are gated behind an explicit confirmation step.

## Run locally

### Option A — Docker (everything at once)

```bash
cp .env.example .env        # fill in GEMINI_API_KEY (optional), etc.
docker compose up --build
# frontend → http://localhost:5173   backend → http://localhost:8000/docs
```

This brings up Postgres, runs migrations, and starts both apps.

### Option B — run each app directly

**Backend** (needs [uv](https://docs.astral.sh/uv/) and a Postgres URL):

```bash
cd backend
uv sync                                  # create .venv + install deps
cp ../.env.example .env                   # set DATABASE_URL, JWT_SECRET, GEMINI_API_KEY
uv run alembic upgrade head               # apply migrations
uv run uvicorn app.main:app --reload      # http://localhost:8000  (docs at /docs)
```

**Frontend** (needs [bun](https://bun.sh)):

```bash
cd frontend
bun install
bun run dev                               # http://localhost:5173
```

> Without an LLM key the chat runs in **echo mode** so the streaming pipe is testable.
> Without a Composio key, Gmail/Calendar calls are **simulated** so the full flow still demos.

## Environment variables

Copy `.env.example` → `.env`. Everything has a sensible default; fill in what you need.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | prod | Postgres connection string (Neon: `postgresql+psycopg://…?sslmode=require`). Omit to use the Docker `db` container. |
| `JWT_SECRET` | ✅ | Signing key for auth cookies — change in production. |
| `LLM_PROVIDER` | — | `gemini` (default) or `openai`. |
| `GEMINI_API_KEY` | for AI | Gemini key. Blank → echo mode. |
| `GEMINI_MODEL` | — | Defaults to `gemini-3.1-flash-lite`. |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | — | Used when `LLM_PROVIDER=openai`. |
| `COMPOSIO_API_KEY` | for Gmail/Calendar | Composio key. Blank → simulated integrations. |
| `COMPOSIO_TIMEZONE` | — | IANA tz for created events (e.g. `Asia/Kolkata`). Defaults to `UTC`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | for Google OAuth | Google sign-in / connection. |
| `VITE_API_BASE_URL` | — | Frontend → backend base URL (default `http://localhost:8000`). |
| `FRONTEND_ORIGIN` | — | Allowed CORS origin(s), comma-separated (default `http://localhost:5173`). |

## Deployment

- **Frontend → Vercel:** SPA + security headers configured in `frontend/vercel.json`. Set
  `VITE_API_BASE_URL` to the Render backend URL.
- **Backend → Render:** `render.yaml` blueprint; migrations run on container start.
- **DB → Neon:** point `DATABASE_URL` at the pooled connection string.

## Tests

```bash
cd backend && uv run pytest          # agent helpers + smoke tests
cd frontend && bun run typecheck     # TypeScript
```
