"""LangGraph wiring + the AI SDK streaming bridge.

Graph:
    START → router ──"extract"──▶ extractor → summarize → END
                   └─"chat"─────▶ respond ─────────────▶ END

`stream_agent` runs the graph and translates LangGraph's dual stream (custom board/tool events +
LLM token messages) into Vercel AI SDK v5 UI message stream parts.
"""

import re
import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agents.conversation import extract_text
from app.agents.nodes.comms import comms_node
from app.agents.nodes.confirm import confirm_node
from app.agents.nodes.edit import edit_node
from app.agents.nodes.extractor import extractor_node
from app.agents.nodes.respond import respond_node
from app.agents.nodes.router import router_node
from app.agents.nodes.summarize import summarize_node
from app.agents.state import GraphState
from app.agents.tools import session_tools
from app.llm.provider import has_llm
from app.services import ai_stream

# Nodes whose LLM tokens should stream to the user as assistant text.
_TEXT_NODES = {"respond", "summarize"}


def _word_chunks(text: str) -> list[str]:
    """Split deterministic node text into word-sized pieces so it streams in instead of popping
    in as one block (keeps trailing whitespace/newlines attached)."""
    return re.findall(r"\s*\S+|\s+", text) or [text]


@lru_cache
def get_graph():
    builder = StateGraph(GraphState)
    builder.add_node("router", router_node)
    builder.add_node("extractor", extractor_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("edit", edit_node)
    builder.add_node("comms", comms_node)
    builder.add_node("confirm", confirm_node)
    builder.add_node("respond", respond_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        lambda s: s["route"],
        {
            "extract": "extractor",
            "edit": "edit",
            "comms": "comms",
            "confirm": "confirm",
            "chat": "respond",
        },
    )
    builder.add_edge("extractor", "summarize")
    builder.add_edge("summarize", END)
    builder.add_edge("edit", END)
    builder.add_edge("comms", END)
    builder.add_edge("confirm", END)
    builder.add_edge("respond", END)
    return builder.compile()


def _initial_messages(history: list[tuple[str, str]], new_message: str) -> list[BaseMessage]:
    msgs: list[BaseMessage] = []
    for role, content in history:
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=new_message))
    return msgs


async def _echo(new_message: str) -> AsyncGenerator[tuple[str, str | None], None]:
    """No-key fallback so the stream is testable without an LLM provider."""
    text_id = uuid.uuid4().hex
    yield ai_stream.sse(ai_stream.start()), None
    yield ai_stream.sse(ai_stream.text_start(text_id)), None
    full = (
        "⚠️ No LLM key configured yet. Echoing your message so the stream is testable: "
        f"{new_message}"
    )
    for word in full.split(" "):
        yield ai_stream.sse(ai_stream.text_delta(text_id, word + " ")), None
    yield ai_stream.sse(ai_stream.text_end(text_id)), None
    yield ai_stream.sse(ai_stream.finish()), None
    yield ai_stream.done(), full


async def stream_agent(
    new_message: str,
    history: list[tuple[str, str]],
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    user_name: str | None = None,
    user_email: str | None = None,
    org_id: uuid.UUID | None = None,
    members: list[dict] | None = None,
) -> AsyncGenerator[tuple[str, str | None], None]:
    """Yield (sse_chunk, final_assistant_text|None) pairs.

    The final tuple carries the full assistant text so the caller can persist it.
    """
    if not has_llm():
        async for pair in _echo(new_message):
            yield pair
        return

    graph = get_graph()
    inputs: GraphState = {
        "messages": _initial_messages(history, new_message),
        "session_id": session_id,
        "user_id": user_id,
        "user_name": user_name,
        "user_email": user_email,
        "org_id": org_id,
        "members": members or [],
        "pending_action": session_tools.get_pending_action(session_id),
    }

    text_id = uuid.uuid4().hex
    text_open = False
    full_text = ""

    yield ai_stream.sse(ai_stream.start()), None

    async for stream_mode, chunk in graph.astream(inputs, stream_mode=["custom", "messages"]):
        if stream_mode == "custom":
            kind = chunk.get("kind")
            if kind == "tool_input":
                yield ai_stream.sse(
                    ai_stream.tool_input(chunk["tool_call_id"], chunk["tool_name"], chunk["input"])
                ), None
            elif kind == "tool_output":
                yield ai_stream.sse(
                    ai_stream.tool_output(chunk["tool_call_id"], chunk["output"])
                ), None
            elif kind == "status":
                # A short "thinking" step (router decision / which node is working).
                yield ai_stream.sse(
                    ai_stream.data_part(
                        "status",
                        {"label": chunk["label"], "node": chunk.get("node")},
                        part_id=uuid.uuid4().hex,
                    )
                ), None
            elif kind == "board":
                item = {k: v for k, v in chunk.items() if k != "kind"}
                yield ai_stream.sse(
                    ai_stream.data_part("action-item", item, part_id=item["id"])
                ), None
            elif kind == "email_draft":
                draft = {k: v for k, v in chunk.items() if k != "kind"}
                yield ai_stream.sse(
                    ai_stream.data_part("email-draft", draft, part_id=uuid.uuid4().hex)
                ), None
            elif kind == "calendar_proposal":
                proposal = {k: v for k, v in chunk.items() if k != "kind"}
                yield ai_stream.sse(
                    ai_stream.data_part("calendar-proposal", proposal, part_id=uuid.uuid4().hex)
                ), None
            elif kind == "say":
                # Deterministic assistant text from a node (edits / drafts / confirmations).
                if not text_open:
                    yield ai_stream.sse(ai_stream.text_start(text_id)), None
                    text_open = True
                full_text += chunk["text"]
                for piece in _word_chunks(chunk["text"]):
                    yield ai_stream.sse(ai_stream.text_delta(text_id, piece)), None
        elif stream_mode == "messages":
            msg_chunk, meta = chunk
            if meta.get("langgraph_node") not in _TEXT_NODES:
                continue
            delta = extract_text(msg_chunk.content)
            if not delta:
                continue
            if not text_open:
                yield ai_stream.sse(ai_stream.text_start(text_id)), None
                text_open = True
            full_text += delta
            yield ai_stream.sse(ai_stream.text_delta(text_id, delta)), None

    if text_open:
        yield ai_stream.sse(ai_stream.text_end(text_id)), None
    yield ai_stream.sse(ai_stream.finish()), None
    yield ai_stream.done(), full_text
