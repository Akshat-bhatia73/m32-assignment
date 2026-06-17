"""LangGraph shared state schema.

Wired up fully in Phase 2 (router -> extractor / scheduler). Defined now so nodes and tools
can import a stable shape.
"""

import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None
    meeting_id: uuid.UUID | None
    route: str  # set by the router node: "extract" | "chat"
    # Action items created this turn (board events), passed from extractor -> summarize.
    extracted: list[dict[str, Any]]
