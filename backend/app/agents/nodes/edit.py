"""Edit node — applies chat-driven changes to existing board items.

The LLM resolves references like "the launch task" to an item id by seeing the current board,
then emits a structured edit plan. We apply each edit deterministically via board_tools and
stream board events + a plain-language confirmation ("say" event).
"""

import uuid
from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.agents.tools import board_tools

EDIT_SYSTEM = (
    "You translate a user's request into changes on their action-item board.\n"
    "Today is {today}. You are given the current board as a JSON list (each item has an id).\n"
    "Return a list of edits. For each edit choose 'op':\n"
    "- 'add': create a NEW action item. Set 'task' (required); optionally 'owner' and 'due_date' "
    "(ISO YYYY-MM-DD, resolving relative dates against today). Leave 'target_id' empty.\n"
    "- 'update': change an EXISTING item. Set 'target_id' to the matching item's id and only the "
    "fields that change. For due_date use an ISO date. To clear an owner or due_date, set the "
    "field to the literal string '__clear__'. Valid status values: open, scheduled, sent, done.\n"
    "- 'delete': remove an existing item (set 'target_id').\n"
    "Match existing items by meaning (task text / owner). If the request asks to create/add a "
    "task, use 'add'. If nothing is actionable, return an empty list."
)


class BoardEdit(BaseModel):
    op: Literal["add", "update", "delete"]
    target_id: str | None = Field(default=None, description="id of the item to update/delete.")
    task: str | None = Field(default=None, description="Task text (required for 'add').")
    owner: str | None = Field(default=None, description="Owner, or '__clear__' to clear.")
    due_date: str | None = Field(default=None, description="ISO date, or '__clear__' to clear.")
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
    user_id = state["user_id"]
    board = board_tools.list_items(session_id)

    request = extract_text(state["messages"][-1].content)

    tool_call_id = uuid.uuid4().hex
    writer(
        {
            "kind": "tool_input",
            "tool_call_id": tool_call_id,
            "tool_name": "update_board",
            "input": {"request": request[:300]},
        }
    )

    llm = get_llm(temperature=0.0).with_structured_output(EditPlan)
    plan: EditPlan = await llm.ainvoke(
        [
            SystemMessage(content=EDIT_SYSTEM.format(today=date.today().isoformat())),
            HumanMessage(content=f"Current board:\n{board}\n\nRequest:\n{request}"),
        ]
    )

    created, updated, deleted = [], [], []
    for edit in plan.edits:
        if edit.op == "add":
            if not edit.task:
                continue
            event = board_tools.add_action_item(
                session_id=session_id,
                user_id=user_id,
                org_id=state.get("org_id"),
                meeting_id=None,
                task=edit.task,
                owner=edit.owner,
                due_date=edit.due_date,
            )
            writer({"kind": "board", **event})
            created.append(event)
        elif edit.op == "delete" and edit.target_id:
            event = board_tools.delete_action_item(edit.target_id)
            if event:
                writer({"kind": "board", **event})
                deleted.append(event)
        elif edit.op == "update" and edit.target_id:
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

    writer(
        {
            "kind": "tool_output",
            "tool_call_id": tool_call_id,
            "output": {
                "added": len(created),
                "updated": len(updated),
                "removed": len(deleted),
            },
        }
    )

    if not created and not updated and not deleted:
        writer(
            {"kind": "say", "text": "I couldn't tell which item you meant. You can ask me to add a "
             "new task, or point me at one on the board to change."}
        )
        return {}

    parts = []
    if created:
        parts.append("Added " + "; ".join(_describe(e) for e in created))
    if updated:
        parts.append("Updated " + "; ".join(_describe(e) for e in updated))
    if deleted:
        parts.append("Removed " + "; ".join(f"“{e['task']}”" for e in deleted))
    writer({"kind": "say", "text": "Done — " + ". ".join(parts) + "."})
    return {}
