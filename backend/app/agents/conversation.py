"""Phase 1 conversation streamer.

Streams an assistant reply token-by-token as AI SDK protocol parts, with in-session memory
loaded from the DB. In Phase 2 this is replaced/extended by the LangGraph router -> extractor /
scheduler graph; the protocol surface (text + data-action-item + tool parts) stays the same.

Falls back to an echo stream when no LLM key is configured, so the streaming pipe is testable
end-to-end without a provider.
"""

import uuid
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.llm.provider import get_llm, has_llm
from app.services import ai_stream

SYSTEM_PROMPT = (
    "You are Meeting → Done, a calm, plain-spoken operations copilot for busy small-business "
    "owners and department heads. Keep replies short, concrete, and free of jargon. When the "
    "user shares meeting notes you will later extract action items; for now, be a helpful, "
    "professional assistant and remember what the user tells you within this conversation."
)


def _extract_text(content: object) -> str:
    """Pull plain text from a LangChain message chunk.

    Gemini 3.x streams content as a list of typed blocks
    (e.g. ``[{"type": "text", "text": "..."}]``); older models / OpenAI use a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _to_lc_messages(history: list[tuple[str, str]], new_message: str) -> list:
    msgs: list = [SystemMessage(content=SYSTEM_PROMPT)]
    for role, content in history:
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=new_message))
    return msgs


async def stream_reply(
    new_message: str,
    history: list[tuple[str, str]],
) -> AsyncGenerator[tuple[str, str | None], None]:
    """Yield (sse_chunk, assistant_text_so_far_final) pairs.

    The second element is None until the stream completes, then carries the full assistant
    text so the caller can persist it.
    """
    text_id = uuid.uuid4().hex
    yield ai_stream.sse(ai_stream.start()), None
    yield ai_stream.sse(ai_stream.text_start(text_id)), None

    full = ""
    if has_llm():
        llm = get_llm()
        messages = _to_lc_messages(history, new_message)
        async for chunk in llm.astream(messages):
            delta = _extract_text(chunk.content)
            if delta:
                full += delta
                yield ai_stream.sse(ai_stream.text_delta(text_id, delta)), None
    else:
        # Echo fallback — proves the streaming contract without an API key.
        full = (
            "⚠️ No LLM key configured yet. Echoing your message so the stream is testable: "
            f"{new_message}"
        )
        for word in full.split(" "):
            yield ai_stream.sse(ai_stream.text_delta(text_id, word + " ")), None

    yield ai_stream.sse(ai_stream.text_end(text_id)), None
    yield ai_stream.sse(ai_stream.finish()), None
    yield ai_stream.done(), full
