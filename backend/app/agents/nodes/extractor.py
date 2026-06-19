"""Extractor node — turns meeting notes into action items on the board.

Structured LLM extraction, then deterministic DB writes via board_tools. Emits a tool part and
one data-action-item part per created item through the LangGraph custom stream.
"""

import uuid
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.people import resolve_owner_name
from app.agents.state import GraphState
from app.agents.tools import board_tools
from app.llm.provider import get_llm

EXTRACTOR_SYSTEM = (
    "You extract concrete action items from meeting notes for a small-business owner.\n"
    "Today's date is {today}. For each action item return:\n"
    "- task: a short imperative description (e.g. 'Send Q3 budget to Priya').\n"
    "- owner: the person responsible if named, else null.\n"
    "- due_date: an ISO date (YYYY-MM-DD) if a deadline is stated or implied "
    "(resolve relative dates like 'Friday' or 'next week' against today's date), else null.\n"
    "Only include real, actionable tasks. Ignore chit-chat. "
    "If there are none, return an empty list."
)


class ExtractedItem(BaseModel):
    task: str = Field(description="Short imperative task description.")
    owner: str | None = Field(default=None, description="Responsible person, or null.")
    due_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD, or null.")


class Extraction(BaseModel):
    items: list[ExtractedItem] = Field(default_factory=list)


async def extractor_node(state: GraphState) -> dict:
    writer = get_stream_writer()
    session_id: uuid.UUID = state["session_id"]
    user_id: uuid.UUID = state["user_id"]
    notes = extract_text(state["messages"][-1].content)

    tool_call_id = uuid.uuid4().hex
    writer(
        {
            "kind": "tool_input",
            "tool_call_id": tool_call_id,
            "tool_name": "extract_action_items",
            "input": {"notes": notes[:500]},
        }
    )

    llm = get_llm(temperature=0.0).with_structured_output(Extraction)
    result: Extraction = await llm.ainvoke(
        [
            SystemMessage(content=EXTRACTOR_SYSTEM.format(today=date.today().isoformat())),
            HumanMessage(content=notes),
        ]
    )

    meeting_id = board_tools.create_meeting(
        session_id=session_id, user_id=user_id, raw_text=notes
    )

    members = state.get("members") or []
    extracted: list[dict] = []
    for item in result.items:
        # Assign the owner to a real teammate when the workspace has members (canonical name),
        # so items land on the right person instead of a loose free-text string.
        owner = resolve_owner_name(item.owner, members)
        event = board_tools.add_action_item(
            session_id=session_id,
            user_id=user_id,
            org_id=state.get("org_id"),
            meeting_id=meeting_id,
            task=item.task,
            owner=owner,
            due_date=item.due_date,
        )
        writer({"kind": "board", **event})
        extracted.append(event)

    writer(
        {"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"created": len(extracted)}}
    )
    return {"meeting_id": meeting_id, "extracted": extracted}
