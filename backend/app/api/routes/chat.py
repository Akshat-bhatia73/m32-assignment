"""Streaming chat endpoint emitting the AI SDK v5 UI message stream protocol."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents.conversation import generate_title
from app.agents.graph import stream_agent
from app.api.deps import CurrentMembership, CurrentUser, DbSession
from app.models import ChatSession, Message
from app.schemas.chat import ChatRequest
from app.services import ai_stream, orgs

# Placeholder titles a fresh session may carry until the first turn names it.
_DEFAULT_TITLES = {"New session", "Workspace", ""}

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    current_user: CurrentUser,
    membership: CurrentMembership,
    db: DbSession,
) -> StreamingResponse:
    session = db.get(ChatSession, payload.session_id)
    if session is None or session.org_id != membership.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    org_id = membership.org_id
    members = orgs.org_roster(db, org_id)

    # Split what the user sees (typed text + attachment chips) from what the agent reads
    # (typed text with the full attachment contents inlined for extraction).
    display_text = payload.message
    if payload.artifacts:
        blob = "\n\n".join(f"--- {a.name} ---\n{a.content}" for a in payload.artifacts)
        agent_input = f"{display_text}\n\n{blob}".strip() if display_text.strip() else blob
    else:
        agent_input = display_text

    if payload.regenerate:
        # Retry: drop the previous assistant reply and reuse the existing last user turn.
        last_assistant = db.scalars(
            select(Message)
            .where(Message.session_id == session.id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
        ).first()
        if last_assistant is not None:
            db.delete(last_assistant)
            db.commit()
        rows = db.scalars(
            select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
        ).all()
        # Exclude the trailing user message — it's the turn we're re-running.
        history = [
            (m.role, m.content)
            for m in (rows[:-1] if rows and rows[-1].role == "user" else rows)
        ]
    else:
        # Persist the user turn first so it survives a dropped connection.
        user_msg = Message(
            session_id=session.id,
            role="user",
            content=display_text,
            artifacts=[a.model_dump() for a in payload.artifacts] or None,
        )
        db.add(user_msg)
        db.commit()

        # Load prior turns for in-session memory (exclude the one we just added at the tail).
        rows = db.scalars(
            select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
        ).all()
        history = [(m.role, m.content) for m in rows if m.id != user_msg.id]
    # Name the session from its first turn so the sidebar reads meaningfully.
    needs_title = not history and (session.title or "").strip() in _DEFAULT_TITLES
    session_id = session.id

    async def generator() -> AsyncGenerator[str, None]:
        assistant_text = ""
        assistant_parts: list[dict] = []
        title_part: str | None = None
        if needs_title:
            title = await generate_title(agent_input)
            session.title = title
            db.commit()
            title_part = ai_stream.sse(
                ai_stream.data_part(
                    "session-title", {"session_id": str(session_id), "title": title}
                )
            )
        try:
            started = False
            async for chunk, final in stream_agent(
                agent_input,
                history,
                session.id,
                current_user.id,
                current_user.name,
                current_user.email,
                org_id=org_id,
                members=members,
                model=payload.model,
                reasoning=payload.reasoning,
            ):
                if final is not None:
                    assistant_text = final["text"]
                    assistant_parts = final["data_parts"]
                yield chunk
                # Emit the new title right after the message envelope's `start` part.
                if title_part and not started:
                    started = True
                    yield title_part
        except Exception as exc:  # surface a protocol error instead of a broken stream
            yield ai_stream.sse(ai_stream.error(f"Agent error: {exc}"))
            yield ai_stream.done()
        finally:
            if assistant_text:
                db.add(
                    Message(
                        session_id=session.id,
                        role="assistant",
                        content=assistant_text,
                        data_parts=assistant_parts or None,
                    )
                )
                db.commit()

    return StreamingResponse(generator(), headers=ai_stream.STREAM_HEADERS)
