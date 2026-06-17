# M32 — "Meeting → Done" Ops Copilot

A chatbot that turns messy meeting notes/transcripts into tracked action items,
follow-up email drafts, and calendar events — with a live Action Board the agent
drives from chat.

> M32 Fullstack + AI take-home project. See [`docs/PLAN.md`](docs/PLAN.md) for the full build plan.

## Stack

- **Frontend:** React 19 + Vite + shadcn/ui (Vercel)
- **Backend:** FastAPI + LangGraph (Render)
- **DB:** Neon (Postgres) via SQLAlchemy + Alembic
- **LLM:** Gemini (free tier), provider-wrapped for OpenAI swap
- **Integrations:** Composio (Gmail + Calendar), Google OAuth

## Status

🚧 Scaffolding. See `docs/PLAN.md` for milestones.
