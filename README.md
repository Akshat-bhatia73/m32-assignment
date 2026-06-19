# [Meeting]32 — "Meeting → Done" Ops Copilot

A chatbot that turns messy meeting notes into **tracked action items, follow-up email drafts, and
calendar events** — with a live **Action Board** the agent drives straight from the chat. Built for
SMB owners and heads of department who don't want another tool to babysit: paste the notes, and the
work gets organized, assigned, and scheduled.

> M32 Fullstack + AI take-home. The name is a play on **M32** → **[Meeting]32**.

**🔗 Live app:** https://m32-assignment.akshat-bhatia.com · **📹 Demo video:** https://drive.google.com/file/d/1y4dJoPyPFAMOKK0d_v_POXGHNB_4wZOL/view?usp=sharing

> ⏱️ **First load may be slow.** The hosted backend runs on Render's free tier, which spins down
> after inactivity. The **first request after a cold start can take ~50–60s** while the service
> wakes up; everything is snappy once it's warm.

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
- **Pick your model** — choose the model that writes your replies (Gemini 3.1 Flash Lite, Gemma 4
  31B, GPT-5.4 Mini, GPT-5.5) right from the composer; GPT-5.5 exposes low / medium / high
  reasoning. Defaults to GPT-5.5 (low) when an OpenAI key is set, otherwise Gemini 3.1 Flash Lite.
- **Workspaces** — shared org board, member invites, multi-session history with auto-titles.

## Stack

| Layer | Tech |
| --- | --- |
| **Frontend** | React 19 + Vite + TypeScript, Tailwind v4, shadcn (Base UI), Vercel AI Elements, **bun** |
| **Backend** | Python 3.12, FastAPI, **LangGraph** multi-agent, SQLAlchemy 2 + Alembic, managed with **uv** |
| **Database** | Neon (Postgres) |
| **LLM** | **User-selectable models** behind one provider wrapper — Google (Gemini 3.1 Flash Lite, Gemma 4 31B) + OpenAI (GPT-5.4 Mini, GPT-5.5 with reasoning) |
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

**Cost-aware model routing.** Each turn fires several internal LLM calls plus one visible
generation, so the two are split into tiers. High-frequency internal work — routing, intent +
reschedule/cancel parsing, yes/no confirmation, action-item extraction, session titles, image OCR —
is pinned to a cheap fixed model (**GPT-5.4 Mini**, with a Gemini fallback when no OpenAI key is
set). Only the user-facing output — chat reply, summary, email draft — uses the model picked in the
UI. The catalog is the single source of truth in `backend/app/llm/models.py`; the per-request
selection is resolved in `app/llm/provider.py` and exposed to the frontend via `GET /models`.

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

> With **no** LLM key (neither Gemini nor OpenAI) the chat runs in **echo mode** so the streaming
> pipe is testable. Set either key to enable real models; set the OpenAI key to unlock the GPT
> models and make GPT-5.5 (low) the default.
> Without a Composio key, Gmail/Calendar calls are **simulated** so the full flow still demos.

## Environment variables

Copy `.env.example` → `.env`. Everything has a sensible default; fill in what you need.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | prod | Postgres connection string (Neon: `postgresql+psycopg://…?sslmode=require`). Omit to use the Docker `db` container. |
| `JWT_SECRET` | ✅ | Signing key for auth cookies — change in production. |
| `GEMINI_API_KEY` | for AI | Enables the Google models (Gemini 3.1 Flash Lite, Gemma 4 31B). |
| `OPENAI_API_KEY` | for AI | Enables the OpenAI models (GPT-5.4 Mini, GPT-5.5) and makes **GPT-5.5 (low)** the default. At least one of the two keys is needed; with neither, chat runs in echo mode. |
| `COMPOSIO_API_KEY` | for Gmail/Calendar | Composio key. Blank → simulated integrations. |
| `COMPOSIO_TIMEZONE` | — | IANA tz for created events (e.g. `Asia/Kolkata`). Defaults to `UTC`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | for Google OAuth | Google sign-in / connection. |
| `VITE_API_BASE_URL` | — | Frontend → backend base URL (default `http://localhost:8000`). |
| `FRONTEND_ORIGIN` | — | Allowed CORS origin(s), comma-separated (default `http://localhost:5173`). |

## Deployment

- **Frontend → Vercel:** SPA + security headers configured in `frontend/vercel.json`. Set
  `VITE_API_BASE_URL` to the Render backend URL.
- **Backend → Render:** `render.yaml` blueprint; migrations run on container start. On the free
  tier the service sleeps after inactivity, so the first request after a cold start can take
  **~50–60s** to respond — subsequent requests are fast.
- **DB → Neon:** point `DATABASE_URL` at the pooled connection string.

## Tests

```bash
cd backend && uv run pytest          # agent helpers + smoke tests
cd frontend && bun run typecheck     # TypeScript
```
