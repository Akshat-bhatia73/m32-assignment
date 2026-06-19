"""Streaming chat endpoint emitting the AI SDK v5 UI message stream protocol."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents.conversation import generate_title
from app.agents.graph import stream_agent
from app.api.deps import CurrentMembership, CurrentUser, DbSession
from app.models import ChatSession, Message, User
from app.schemas.chat import ChatRequest
from app.services import ai_stream, orgs

# Placeholder titles a fresh session may carry until the first turn names it.
_DEFAULT_TITLES = {"New session", "Workspace", ""}

router = APIRouter(prefix="/chat", tags=["chat"])


def _message_context(message: Message) -> str:
    """Rebuild the text the agent originally saw for a persisted user turn."""
    if message.role != "user" or not message.artifacts:
        return message.content
    blob = "\n\n".join(
        f"--- {artifact.get('name', 'Attachment')} ---\n{artifact.get('content', '')}"
        for artifact in message.artifacts
    )
    return f"{message.content}\n\n{blob}".strip() if message.content.strip() else blob


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
    # Workspaces share sessions read-only: only the person who started a chat can post to it, so
    # there's a single writer per thread — no two members streaming into one conversation at once.
    if session.user_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This chat is read-only — only the person who started it can send messages.",
        )
    org_id = membership.org_id
    members = orgs.org_roster(db, org_id)

    # Follow-up emails are drafted in the name of whoever started this session (the meeting owner),
    # not the current viewer — so a shared session keeps one consistent sender no matter who opens
    # or continues it. Fall back to the current user for legacy sessions with no recorded creator.
    creator = db.get(User, session.user_id)
    organizer_name = creator.name if creator else current_user.name
    organizer_email = creator.email if creator else current_user.email

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
            (m.role, _message_context(m))
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
        history = [(m.role, _message_context(m)) for m in rows if m.id != user_msg.id]
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
                organizer_name=organizer_name,
                organizer_email=organizer_email,
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
