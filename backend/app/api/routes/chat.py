"""Streaming chat endpoint emitting the AI SDK v5 UI message stream protocol."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents.conversation import stream_reply
from app.api.deps import CurrentUser, DbSession
from app.models import ChatSession, Message
from app.schemas.chat import ChatRequest
from app.services import ai_stream

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
def chat_stream(
    payload: ChatRequest, current_user: CurrentUser, db: DbSession
) -> StreamingResponse:
    session = db.get(ChatSession, payload.session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    # Persist the user turn first so it survives a dropped connection.
    user_msg = Message(session_id=session.id, role="user", content=payload.message)
    db.add(user_msg)
    db.commit()

    # Load prior turns for in-session memory (exclude the one we just added at the tail).
    rows = db.scalars(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
    ).all()
    history = [(m.role, m.content) for m in rows if m.id != user_msg.id]

    async def generator() -> AsyncGenerator[str, None]:
        assistant_text = ""
        try:
            async for chunk, final in stream_reply(payload.message, history):
                if final is not None:
                    assistant_text = final
                yield chunk
        except Exception as exc:  # surface a protocol error instead of a broken stream
            yield ai_stream.sse(ai_stream.error(f"Agent error: {exc}"))
            yield ai_stream.done()
        finally:
            if assistant_text:
                db.add(
                    Message(session_id=session.id, role="assistant", content=assistant_text)
                )
                db.commit()

    return StreamingResponse(generator(), headers=ai_stream.STREAM_HEADERS)
