"""Confirm node — executes (or cancels) the session's pending external action.

Reached only when a pending action exists. Determines yes/no/unclear, then runs the gated call
via the Composio seam (simulated until a key is set), updates the board, and clears the pending
action. This is the only place external side effects happen.
"""

import logging
import uuid
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.agents.tools import board_tools, composio_tools, session_tools

logger = logging.getLogger(__name__)

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
        tool_call_id = uuid.uuid4().hex
        writer(
            {
                "kind": "tool_input",
                "tool_call_id": tool_call_id,
                "tool_name": "send_email",
                "input": {"to": pending["to"], "subject": pending["subject"]},
            }
        )
        result = composio_tools.send_gmail(
            user_id=composio_user_id,
            to=pending["to"],
            subject=pending["subject"],
            body=pending["body"],
        )
        status = result.get("status")
        writer({"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"status": status}})
        if status == "error":
            detail = result.get("error")
            # Log the real Composio error server-side (the usual cause is the connected account's
            # external user_id not matching the app-login email we send as).
            logger.error("Gmail send failed for user_id=%s: %s", composio_user_id, detail)
            hint = f" (details: {detail})" if detail else ""
            writer(
                {"kind": "say", "text": "I couldn't send it. Gmail may not be connected for "
                 f"{composio_user_id}, or the connection isn't active — check Settings and try "
                 f"again.{hint}"}
            )
            return {}  # keep the pending action so a retry works
        session_tools.set_pending_action(session_id, None)
        sim = " (simulated — add a Composio key to send for real)" if status == "simulated" else ""
        writer(
            {"kind": "say", "text": f"Sent the follow-up to {', '.join(pending['to'])}{sim}."}
        )
        return {}

    if action_type == "create_events":
        events_pending = pending.get("events", [])
        tool_call_id = uuid.uuid4().hex
        writer(
            {
                "kind": "tool_input",
                "tool_call_id": tool_call_id,
                "tool_name": "create_calendar_events",
                "input": {"events": len(events_pending)},
            }
        )
        created, failed = 0, 0
        last_error: str | None = None
        for event in events_pending:
            res = composio_tools.create_calendar_event(
                user_id=composio_user_id, summary=event["summary"], event_date=event["date"]
            )
            if res.get("status") == "error":
                failed += 1
                last_error = res.get("error") or last_error
                continue
            board_event = board_tools.set_status(
                event["action_item_id"], "scheduled", external_ref=res.get("event_id")
            )
            if board_event:
                writer({"kind": "board", **board_event})
            created += 1
        writer(
            {
                "kind": "tool_output",
                "tool_call_id": tool_call_id,
                "output": {"created": created, "failed": failed},
            }
        )
        if created == 0 and failed:
            logger.error(
                "Calendar create failed for user_id=%s: %s", composio_user_id, last_error
            )
            hint = f" (details: {last_error})" if last_error else ""
            writer(
                {"kind": "say", "text": "I couldn't add those events. Google Calendar may not be "
                 f"connected for {composio_user_id}, or the connection isn't active — check "
                 f"Settings and try again.{hint}"}
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

    if action_type == "reschedule_event":
        tool_call_id = uuid.uuid4().hex
        writer({
            "kind": "tool_input", "tool_call_id": tool_call_id, "tool_name": "reschedule_event",
            "input": {"summary": pending.get("summary"), "start": pending.get("start_datetime")},
        })
        res = composio_tools.update_calendar_event(
            user_id=composio_user_id,
            event_id=pending["event_id"],
            start_datetime=pending["start_datetime"],
            # Pass the title through — Google's update replaces the event, so omitting the summary
            # would blank it out (the old "[no title]" bug).
            summary=pending.get("summary"),
        )
        status = res.get("status")
        writer({"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"status": status}})
        if status == "error":
            detail = res.get("error")
            logger.error("Calendar reschedule failed for user_id=%s: %s", composio_user_id, detail)
            hint = f" (details: {detail})" if detail else ""
            writer({"kind": "say", "text": "I couldn't move that event. Google Calendar may not "
                    f"be connected for {composio_user_id} — check Settings and try again.{hint}"})
            return {}  # keep pending for retry
        # Reflect the new date + title on the board item.
        new_date = pending["start_datetime"].split("T")[0]
        board_event = board_tools.update_action_item(
            pending["action_item_id"], task=pending.get("summary"), due_date=new_date
        )
        if board_event:
            writer({"kind": "board", **board_event})
        session_tools.set_pending_action(session_id, None)
        sim = " (simulated — add a Composio key to update it for real)" if status == "simulated" \
            else ""
        when = pending["start_datetime"].replace("T", " at ")
        writer({"kind": "say", "text": f"Updated “{pending['summary']}” — now {when}{sim}."})
        return {}

    if action_type == "delete_event":
        tool_call_id = uuid.uuid4().hex
        writer({
            "kind": "tool_input", "tool_call_id": tool_call_id, "tool_name": "delete_event",
            "input": {"summary": pending.get("summary")},
        })
        res = composio_tools.delete_calendar_event(
            user_id=composio_user_id, event_id=pending["event_id"]
        )
        status = res.get("status")
        writer({"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"status": status}})
        if status == "error":
            detail = res.get("error")
            logger.error("Calendar delete failed for user_id=%s: %s", composio_user_id, detail)
            hint = f" (details: {detail})" if detail else ""
            writer({"kind": "say", "text": "I couldn't remove that event. Google Calendar may not "
                    f"be connected for {composio_user_id} — check Settings and try again.{hint}"})
            return {}  # keep pending for retry
        # Reopen the task and drop the calendar link now that the event is gone.
        board_event = board_tools.set_status(
            pending["action_item_id"], "open", external_ref=""
        )
        if board_event:
            writer({"kind": "board", **board_event})
        session_tools.set_pending_action(session_id, None)
        sim = " (simulated — add a Composio key to remove it for real)" if status == "simulated" \
            else ""
        writer({"kind": "say", "text": f"Removed “{pending['summary']}” from your calendar and "
                f"reopened the task{sim}."})
        return {}

    # Unknown / stale pending action.
    session_tools.set_pending_action(session_id, None)
    writer({"kind": "say", "text": "That request expired — could you tell me again what you'd "
            "like to do?"})
    return {}
