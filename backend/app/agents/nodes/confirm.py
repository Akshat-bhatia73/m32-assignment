"""Confirm node — executes (or cancels) the session's pending external action.

Reached only when a pending action exists. Determines yes/no/unclear, then runs the gated call
via the Composio seam (simulated until a key is set), updates the board, and clears the pending
action. This is the only place external side effects happen.
"""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.agents.tools import board_tools, composio_tools, session_tools

_YES = {"yes", "y", "yep", "yeah", "yup", "sure", "ok", "okay", "go ahead", "do it",
        "send", "send it", "confirm", "confirmed", "please do", "go for it"}
_NO = {"no", "n", "nope", "cancel", "stop", "don't", "dont", "not now", "hold off", "wait"}


class Affirmation(BaseModel):
    decision: Literal["yes", "no", "unclear"]


def _quick_decision(message: str) -> str | None:
    low = message.strip().lower().rstrip("!.")
    if low in _YES:
        return "yes"
    if low in _NO:
        return "no"
    return None


async def _decide(message: str) -> str:
    quick = _quick_decision(message)
    if quick:
        return quick
    from app.llm.provider import get_llm

    llm = get_llm(temperature=0.0).with_structured_output(Affirmation)
    result: Affirmation = await llm.ainvoke(
        [
            SystemMessage(
                content="Is the user confirming a pending action? Answer yes, no, or unclear."
            ),
            HumanMessage(content=message),
        ]
    )
    return result.decision


async def confirm_node(state: GraphState) -> dict:
    writer = get_stream_writer()
    session_id = state["session_id"]
    pending = state.get("pending_action") or {}
    message = extract_text(state["messages"][-1].content)

    decision = await _decide(message)
    if decision == "no":
        session_tools.set_pending_action(session_id, None)
        writer({"kind": "say", "text": "No problem — I'll hold off. Nothing was sent."})
        return {}
    if decision == "unclear":
        writer({"kind": "say", "text": "Just to confirm — should I go ahead? (yes / no)"})
        return {}

    composio_user_id = state.get("user_email") or str(session_id)
    action_type = pending.get("type")
    if action_type == "send_email":
        result = composio_tools.send_gmail(
            user_id=composio_user_id,
            to=pending["to"],
            subject=pending["subject"],
            body=pending["body"],
        )
        status = result.get("status")
        if status == "error":
            writer(
                {"kind": "say", "text": "I couldn't send it — your Gmail account may not be "
                 "connected yet. Once Gmail is connected in Composio, try again."}
            )
            return {}  # keep the pending action so a retry works
        session_tools.set_pending_action(session_id, None)
        sim = " (simulated — add a Composio key to send for real)" if status == "simulated" else ""
        writer(
            {"kind": "say", "text": f"Sent the follow-up to {', '.join(pending['to'])}{sim}."}
        )
        return {}

    if action_type == "create_events":
        created, failed = 0, 0
        for event in pending.get("events", []):
            res = composio_tools.create_calendar_event(
                user_id=composio_user_id, summary=event["summary"], event_date=event["date"]
            )
            if res.get("status") == "error":
                failed += 1
                continue
            board_event = board_tools.set_status(
                event["action_item_id"], "scheduled", external_ref=res.get("event_id")
            )
            if board_event:
                writer({"kind": "board", **board_event})
            created += 1
        if created == 0 and failed:
            writer(
                {"kind": "say", "text": "I couldn't add those events — your Google Calendar may "
                 "not be connected yet. Once it's connected in Composio, try again."}
            )
            return {}  # keep pending for retry
        session_tools.set_pending_action(session_id, None)
        sim = (
            " (simulated — add a Composio key to create them for real)"
            if not composio_tools.composio_enabled()
            else ""
        )
        tail = f" ({failed} couldn't be created)" if failed else ""
        writer(
            {"kind": "say", "text": f"Added {created} event{'s' if created != 1 else ''} to your "
             f"calendar and marked those items as scheduled{sim}{tail}."}
        )
        return {}

    # Unknown / stale pending action.
    session_tools.set_pending_action(session_id, None)
    writer({"kind": "say", "text": "That request expired — could you tell me again what you'd "
            "like to do?"})
    return {}
