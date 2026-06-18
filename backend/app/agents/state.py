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
    user_email: str | None
    org_id: uuid.UUID | None
    # Org roster [{id, name, email, role}] — used to resolve action-item owners to teammate emails.
    members: list[dict[str, Any]]
    meeting_id: uuid.UUID | None
    route: str  # set by the router: "extract" | "edit" | "comms" | "confirm" | "chat"
    # Action items created this turn (board events), passed from extractor -> summarize.
    extracted: list[dict[str, Any]]
    # External action awaiting confirmation (loaded from the session at turn start).
    pending_action: dict[str, Any] | None
