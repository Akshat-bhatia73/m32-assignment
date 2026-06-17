"""Edit node — applies chat-driven changes to existing board items.

The LLM resolves references like "the launch task" to an item id by seeing the current board,
then emits a structured edit plan. We apply each edit deterministically via board_tools and
stream board events + a plain-language confirmation ("say" event).
"""

from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.agents.tools import board_tools

EDIT_SYSTEM = (
    "You translate a user's request into edits on their action-item board.\n"
    "Today is {today}. You are given the current board as a JSON list (each item has an id).\n"
    "Return a list of edits. For each edit set 'target_id' to the matching item's id and 'op':\n"
    "- 'update': change fields. Set only the fields that change. For due_date use an ISO date "
    "(YYYY-MM-DD), resolving relative dates against today. To clear an owner or due_date, set the "
    "field to the literal string '__clear__'. Valid status values: open, scheduled, sent, done.\n"
    "- 'delete': remove the item.\n"
    "Match items by meaning (task text / owner). If nothing matches, return an empty list."
)


class BoardEdit(BaseModel):
    target_id: str = Field(description="id of the item to edit, from the provided board.")
    op: Literal["update", "delete"]
    task: str | None = None
    owner: str | None = Field(default=None, description="New owner, or '__clear__'.")
    due_date: str | None = Field(default=None, description="ISO date, or '__clear__'.")
    status: Literal["open", "scheduled", "sent", "done"] | None = None


class EditPlan(BaseModel):
    edits: list[BoardEdit] = Field(default_factory=list)


def _describe(event: dict) -> str:
    bits = [f"“{event['task']}”"]
    if event.get("owner"):
        bits.append(f"owner {event['owner']}")
    if event.get("due_date"):
        bits.append(f"due {event['due_date']}")
    if event.get("status") and event["status"] != "open":
        bits.append(event["status"])
    return " · ".join(bits)


async def edit_node(state: GraphState) -> dict:
    from app.llm.provider import get_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    board = board_tools.list_items(session_id)

    if not board:
        writer({"kind": "say", "text": "Your board is empty, so there's nothing to change yet."})
        return {}

    request = extract_text(state["messages"][-1].content)
    llm = get_llm(temperature=0.0).with_structured_output(EditPlan)
    plan: EditPlan = await llm.ainvoke(
        [
            SystemMessage(content=EDIT_SYSTEM.format(today=date.today().isoformat())),
            HumanMessage(content=f"Current board:\n{board}\n\nRequest:\n{request}"),
        ]
    )

    updated, deleted = [], []
    for edit in plan.edits:
        if edit.op == "delete":
            event = board_tools.delete_action_item(edit.target_id)
            if event:
                writer({"kind": "board", **event})
                deleted.append(event)
        else:
            event = board_tools.update_action_item(
                edit.target_id,
                task=edit.task,
                owner=edit.owner,
                due_date=edit.due_date,
                status=edit.status,
            )
            if event:
                writer({"kind": "board", **event})
                updated.append(event)

    if not updated and not deleted:
        writer(
            {"kind": "say", "text": "I couldn't match that to an item on the board. "
             "Could you say which task you mean?"}
        )
        return {}

    parts = []
    if updated:
        parts.append("Updated " + "; ".join(_describe(e) for e in updated))
    if deleted:
        parts.append("Removed " + "; ".join(f"“{e['task']}”" for e in deleted))
    writer({"kind": "say", "text": "Done — " + ". ".join(parts) + "."})
    return {}
