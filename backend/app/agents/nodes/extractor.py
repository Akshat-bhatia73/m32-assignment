"""Extractor node — summarizes meeting notes and proposes action items for approval."""

import uuid
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.people import resolve_owner_name
from app.agents.state import GraphState
from app.agents.tools import session_tools
from app.llm.provider import get_classifier_llm

EXTRACTOR_SYSTEM = (
    "You summarize meeting notes and extract concrete action items for a small-business owner.\n"
    "Write a concise factual summary covering the main discussion, decisions, and unresolved "
    "questions. Do not reduce the meeting to a task list.\n"
    "Today's date is {today}. For each action item return:\n"
    "- task: a short imperative description (e.g. 'Send Q3 budget to Priya').\n"
    "- owner: the person responsible if named, else null.\n"
    "- due_date: an ISO date (YYYY-MM-DD) if a deadline is stated or implied "
    "(resolve relative dates like 'Friday' or 'next week' against today's date), else null.\n"
    "Use ONLY information present in the notes. Do NOT invent tasks, people, or deadlines. If an "
    "owner is not named, set owner to null — never guess a name. If no due date is stated or "
    "clearly implied, set due_date to null — never guess a date. Only include real, actionable "
    "tasks. Ignore chit-chat. If there are none, return an empty list."
)


class ExtractedItem(BaseModel):
    task: str = Field(description="Short imperative task description.")
    owner: str | None = Field(default=None, description="Responsible person, or null.")
    due_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD, or null.")


class Extraction(BaseModel):
    summary: str = Field(description="Concise factual meeting summary in 1-3 short paragraphs.")
    items: list[ExtractedItem] = Field(default_factory=list)


async def extractor_node(state: GraphState) -> dict:
    writer = get_stream_writer()
    session_id = state["session_id"]
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

    llm = get_classifier_llm().with_structured_output(Extraction)
    result: Extraction = await llm.ainvoke(
        [
            SystemMessage(content=EXTRACTOR_SYSTEM.format(today=date.today().isoformat())),
            HumanMessage(content=notes),
        ]
    )

    members = state.get("members") or []
    extracted: list[dict] = []
    for item in result.items:
        # Assign the owner to a real teammate when the workspace has members (canonical name),
        # so items land on the right person instead of a loose free-text string.
        owner = resolve_owner_name(item.owner, members)
        extracted.append({"task": item.task, "owner": owner, "due_date": item.due_date})

    pending = (
        {"type": "add_action_items", "items": extracted, "notes": notes} if extracted else None
    )
    session_tools.set_pending_action(session_id, pending)
    writer(
        {
            "kind": "tool_output",
            "tool_call_id": tool_call_id,
            "output": {"proposed": len(extracted)},
        }
    )
    return {"meeting_summary": result.summary, "extracted": extracted}
