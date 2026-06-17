"""Router node — classifies each user turn into a route."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.llm.provider import get_llm

ROUTER_SYSTEM = (
    "You route a user's latest message in an operations-copilot chat. Choose one route:\n"
    "- 'extract': the message contains meeting notes / a transcript, or asks to pull action "
    "items / tasks / to-dos / follow-ups out of notes.\n"
    "- 'edit': a request to change EXISTING board items — reassign an owner, change a due date, "
    "rename, mark done/scheduled, or delete an item.\n"
    "- 'comms': a request to draft or send a follow-up EMAIL, or to SCHEDULE items / add them to "
    "the calendar.\n"
    "- 'confirm': a short yes/no-style reply (e.g. 'yes', 'go ahead', 'no', 'cancel'). Only pick "
    "this when there is a pending action awaiting confirmation.\n"
    "- 'chat': greetings, questions, or anything else.\n"
    "Decide based on the latest message and whether a pending action exists."
)


class RouteDecision(BaseModel):
    route: Literal["extract", "edit", "comms", "confirm", "chat"] = Field(
        description="Where to send this turn."
    )


async def router_node(state: GraphState) -> dict:
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
    return {"route": route}
