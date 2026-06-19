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
    # The current viewer (used to address them by name + send from their own connected account).
    user_name: str | None
    user_email: str | None
    # The session's creator — the "meeting owner". Follow-up emails are drafted in their name so a
    # shared session keeps one consistent sender no matter who opens or continues it.
    organizer_name: str | None
    organizer_email: str | None
    org_id: uuid.UUID | None
    # Org roster [{id, name, email, role}] — used to resolve action-item owners to teammate emails.
    members: list[dict[str, Any]]
    meeting_id: uuid.UUID | None
    route: str  # set by the router: "extract" | "edit" | "comms" | "confirm" | "chat"
    # Action items proposed from meeting notes, passed from extractor -> summarize.
    extracted: list[dict[str, Any]]
    meeting_summary: str | None
    # External action awaiting confirmation (loaded from the session at turn start).
    pending_action: dict[str, Any] | None
