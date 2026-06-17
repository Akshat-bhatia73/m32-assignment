# Backend — Meeting → Done Ops Copilot

FastAPI + LangGraph + SQLAlchemy/Alembic on Neon (Postgres). Managed with **uv** (Python 3.12).

## Setup

```bash
cd backend
uv sync                      # create .venv + install deps (incl. dev group)
cp .env.example .env         # then fill in DATABASE_URL, JWT_SECRET, GEMINI_API_KEY
```

## Database migrations (Alembic)

```bash
uv run alembic revision --autogenerate -m "init schema"   # generate from models
uv run alembic upgrade head                               # apply
```

The DB URL is read from `app.config` (env / `.env`) — never hardcoded in `alembic.ini`.

## Run

```bash
uv run uvicorn app.main:app --reload
# http://localhost:8000/health  ·  docs at /docs
```

Without an LLM key set, `/chat/stream` returns an **echo** stream so the AI SDK protocol pipe is
testable end-to-end before wiring Gemini.

## Layout

```
app/
  main.py        FastAPI app + CORS + routers
  config.py      pydantic-settings
  database.py    engine / session / Base
  models/        SQLAlchemy: user, chat_session, message, meeting, action_item
  schemas/       Pydantic request/response models
  api/routes/    auth, sessions, chat, meetings, actions
  auth/          jwt, password (bcrypt)
  agents/        LangGraph state + conversation streamer (graph nodes/tools land in Phase 2)
  llm/provider.py  Gemini default, one-line OpenAI swap
  services/ai_stream.py  AI SDK v5 UI message stream protocol helpers
```

## Streaming protocol

`POST /chat/stream` emits the **Vercel AI SDK v5 UI message stream** (SSE): `start`,
`text-start`/`text-delta`/`text-end`, `finish`, then `[DONE]`. Phase 2 adds `tool-*` parts and
custom `data-action-item` parts that drive the live Action Board.
