"""Router node — classifies each user turn into a route."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.llm.provider import get_llm

ROUTER_SYSTEM = (
    "You route a user's latest message in an operations-copilot chat. Choose one route:\n"
    "- 'extract': the message contains meeting notes / a transcript, or asks to pull action "
    "items / tasks / to-dos / follow-ups out of notes.\n"
    "- 'edit': a request to add, change, or remove board TASKS — create/add a new task, reassign "
    "an owner, change a due date, rename a task, mark done/scheduled, or delete a task.\n"
    "- 'comms': a request to draft or send a follow-up EMAIL, to SCHEDULE items / add them to "
    "the calendar, to MOVE / RESCHEDULE / push back an existing calendar event, to RENAME a "
    "calendar event, or to CANCEL / REMOVE / DELETE an existing calendar event.\n"
    "- 'confirm': a short yes/no-style reply (e.g. 'yes', 'go ahead', 'no', 'cancel'). Only pick "
    "this when there is a pending action awaiting confirmation.\n"
    "- 'chat': greetings, questions, or anything else.\n"
    "Decide based on the latest message and whether a pending action exists."
)


class RouteDecision(BaseModel):
    route: Literal["extract", "edit", "comms", "confirm", "chat"] = Field(
        description="Where to send this turn."
    )


# Human-readable next-step label per route, surfaced as a "thinking" step.
_ROUTE_STEPS = {
    "extract": "Reading your notes",
    "edit": "Updating the board",
    "comms": "Preparing communications",
    "confirm": "Carrying that out",
    "chat": "Thinking",
}


async def router_node(state: GraphState) -> dict:
    writer = get_stream_writer()
    writer({"kind": "status", "node": "router", "label": "Understanding your request"})
    last = extract_text(state["messages"][-1].content)
    pending = state.get("pending_action")
    pending_note = (
        f"A pending action is awaiting confirmation (type: {pending.get('type')})."
        if pending
        else "There is no pending action."
    )
    llm = get_llm(temperature=0.0).with_structured_output(RouteDecision)
    decision: RouteDecision = await llm.ainvoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"{pending_note}\n\nLatest message:\n{last}"),
        ]
    )
    route = decision.route
    # Guard: 'confirm' only makes sense with a pending action.
    if route == "confirm" and not pending:
        route = "chat"
    writer({"kind": "status", "node": route, "label": _ROUTE_STEPS.get(route, "Working")})
    return {"route": route}
