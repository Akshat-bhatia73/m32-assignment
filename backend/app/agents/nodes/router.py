"""Router node — classifies each user turn into a route."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.llm.provider import get_classifier_llm

ROUTER_SYSTEM = (
    "You route a user's latest message in an operations-copilot chat.\n\n"
    "FIRST, decide whether the user is ASKING (a question, or wanting information / advice / a "
    "suggestion) or DIRECTING (telling you to perform an action now). Only DIRECTING messages "
    "should trigger an action route (extract / edit / comms). When the user is merely asking what "
    "should be done, what needs an email or event, whether to follow up, or for your opinion, "
    "route to 'chat' and ANSWER — do NOT draft, schedule, or change anything until they ask.\n\n"
    "Choose one route:\n"
    "- 'extract': the message contains meeting notes / a transcript, or explicitly asks to pull "
    "action items / tasks / to-dos / follow-ups out of notes.\n"
    "- 'edit': a request to add, change, or remove board TASKS — create/add a new task, reassign "
    "an owner, change a due date, rename a task, mark done/scheduled, or delete a task.\n"
    "- 'comms': a DIRECTIVE to act on EMAIL or the user's CALENDAR — draft/send a follow-up "
    "EMAIL; SCHEDULE items / add them to the calendar; MOVE / RESCHEDULE / push back an event; "
    "RENAME an event; CANCEL / REMOVE / DELETE an existing calendar event; or a direct request to "
    "VIEW / CHECK / LIST what is actually on the user's calendar ('what's on my calendar today?'). "
    "Do NOT pick 'comms' for open questions like 'what emails need to be set up?', 'any calendar "
    "events I should add?', or 'should I email the team?' — those are 'chat'.\n"
    "- 'confirm': a short yes/no-style reply (e.g. 'yes', 'go ahead', 'no', 'cancel'). Only pick "
    "this when there is a pending action awaiting confirmation.\n"
    "- 'chat': greetings, questions, requests for information / advice / suggestions, or anything "
    "else that doesn't clearly direct you to perform one of the actions above.\n\n"
    "Decide based on the latest message and whether a pending action exists. When in doubt between "
    "an action route and 'chat', prefer 'chat'."
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

_CONFIRM_YES = {
    "yes",
    "y",
    "yep",
    "yeah",
    "yup",
    "sure",
    "ok",
    "okay",
    "go ahead",
    "do it",
    "send",
    "send it",
    "confirm",
    "confirmed",
    "please do",
    "go for it",
}
_CONFIRM_NO = {"no", "n", "nope", "cancel", "stop", "don't", "dont", "not now", "hold off", "wait"}


def _is_explicit_confirmation(message: str) -> bool:
    """Only short, unambiguous confirmation replies may execute a pending action."""
    normalized = message.strip().lower().rstrip("!.")
    return normalized in _CONFIRM_YES or normalized in _CONFIRM_NO


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
    llm = get_classifier_llm().with_structured_output(RouteDecision)
    decision: RouteDecision = await llm.ainvoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"{pending_note}\n\nLatest message:\n{last}"),
        ]
    )
    route = decision.route
    # Safety boundary: pending state must not turn questions, corrections, or discussion into
    # approval. Only a small explicit phrase can enter the side-effecting confirmation node.
    if route == "confirm" and (not pending or not _is_explicit_confirmation(last)):
        route = "chat"
    writer({"kind": "status", "node": route, "label": _ROUTE_STEPS.get(route, "Working")})
    return {"route": route}
