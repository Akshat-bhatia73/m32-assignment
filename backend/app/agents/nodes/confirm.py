"""Confirm node — executes (or cancels) the session's pending external action.

Reached only when a pending action exists. Determines yes/no/unclear, then runs the gated call
via the Composio seam (simulated until a key is set), updates the board, and clears the pending
action. This is the only place external side effects happen.
"""

import logging
import re
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
    # A click on a specific draft is itself the single approval. Do not ask for a second yes/no.
    if re.fullmatch(r"send draft [a-f0-9]+", low) or low == "send all drafts":
        return "yes"
    if low in _YES:
        return "yes"
    if low in _NO:
        return "no"
    return None


async def _decide(message: str) -> str:
    quick = _quick_decision(message)
    if quick:
        return quick
    from app.llm.provider import get_classifier_llm

    llm = get_classifier_llm().with_structured_output(Affirmation)
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

    # Card actions can target one draft without affecting the rest of the pending batch.
    if pending.get("type") == "send_emails":
        dismiss_match = re.fullmatch(r"dismiss draft ([a-f0-9]+)", message.strip().lower())
        if dismiss_match:
            draft_id = dismiss_match.group(1)
            remaining = [d for d in pending.get("drafts", []) if d.get("draft_id") != draft_id]
            session_tools.set_pending_action(
                session_id,
                {"type": "send_emails", "drafts": remaining} if remaining else None,
            )
            writer({"kind": "say", "text": "Dismissed that draft. Nothing was sent."})
            return {}

    decision = await _decide(message)
    if decision == "no":
        session_tools.set_pending_action(session_id, None)
        writer({"kind": "say", "text": "No problem — I'll hold off. Nothing was changed."})
        return {}
    if decision == "unclear":
        writer({"kind": "say", "text": "Just to confirm — should I go ahead? (yes / no)"})
        return {}

    composio_user_id = state.get("user_email") or str(session_id)
    action_type = pending.get("type")
    if action_type == "add_action_items":
        notes = pending.get("notes", "")
        meeting_id = board_tools.create_meeting(
            session_id=session_id, user_id=state["user_id"], raw_text=notes
        )
        created = []
        for item in pending.get("items", []):
            event = board_tools.add_action_item(
                session_id=session_id,
                user_id=state["user_id"],
                org_id=state.get("org_id"),
                meeting_id=meeting_id,
                task=item["task"],
                owner=item.get("owner"),
                due_date=item.get("due_date"),
            )
            writer({"kind": "board", **event})
            created.append(event)
        session_tools.set_pending_action(session_id, None)
        count = len(created)
        suffix = "s" if count != 1 else ""
        writer({"kind": "say", "text": f"Added {count} action item{suffix} to the board."})
        return {"meeting_id": meeting_id, "extracted": created}

    if action_type in {"send_email", "send_emails"}:
        all_drafts = pending.get("drafts") or [pending]
        target_match = re.fullmatch(r"send draft ([a-f0-9]+)", message.strip().lower())
        target_id = target_match.group(1) if target_match else None
        drafts = [d for d in all_drafts if not target_id or d.get("draft_id") == target_id]
        untouched = [d for d in all_drafts if target_id and d.get("draft_id") != target_id]
        if not drafts:
            writer({"kind": "say", "text": "That draft is no longer pending."})
            return {}
        tool_call_id = uuid.uuid4().hex
        writer(
            {
                "kind": "tool_input",
                "tool_call_id": tool_call_id,
                "tool_name": "send_email",
                "input": {"drafts": len(drafts)},
            }
        )
        sent, failed, simulated = 0, 0, False
        failed_drafts = []
        detail = None
        for draft in drafts:
            result = composio_tools.send_gmail(
                user_id=composio_user_id,
                to=draft["to"],
                subject=draft["subject"],
                body=draft["body"],
            )
            if result.get("status") == "error":
                failed += 1
                failed_drafts.append(draft)
                detail = result.get("error") or detail
            else:
                sent += 1
                simulated = simulated or result.get("status") == "simulated"
        writer({"kind": "tool_output", "tool_call_id": tool_call_id,
                "output": {"sent": sent, "failed": failed}})
        if not sent and failed:
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
        remaining = untouched + failed_drafts
        session_tools.set_pending_action(
            session_id,
            {"type": "send_emails", "drafts": remaining} if remaining else None,
        )
        sim = " (simulated — add a Composio key to send for real)" if simulated else ""
        tail = f" {failed} failed." if failed else ""
        writer({"kind": "say", "text": f"Sent {sent} email{'s' if sent != 1 else ''}{sim}.{tail}"})
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
        # Reflect the new date + title on the board item, if this event is linked to one.
        if pending.get("action_item_id"):
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

    if action_type in ("delete_event", "delete_events"):
        # Normalize singular + plural into one list of {event_id, summary, action_item_id}.
        targets = pending.get("events") or [
            {"event_id": pending.get("event_id"), "summary": pending.get("summary"),
             "action_item_id": pending.get("action_item_id")}
        ]
        tool_call_id = uuid.uuid4().hex
        writer({
            "kind": "tool_input", "tool_call_id": tool_call_id, "tool_name": "delete_events",
            "input": {"events": len(targets)},
        })
        removed, failed, sim_any = [], 0, False
        last_error: str | None = None
        for ev in targets:
            res = composio_tools.delete_calendar_event(
                user_id=composio_user_id, event_id=ev["event_id"]
            )
            status = res.get("status")
            if status == "error":
                failed += 1
                last_error = res.get("error") or last_error
                continue
            sim_any = sim_any or status == "simulated"
            # Reopen the linked task (if any) now that the event is gone.
            if ev.get("action_item_id"):
                board_event = board_tools.set_status(
                    ev["action_item_id"], "open", external_ref=""
                )
                if board_event:
                    writer({"kind": "board", **board_event})
            removed.append(ev.get("summary") or "(no title)")
        writer({"kind": "tool_output", "tool_call_id": tool_call_id,
                "output": {"removed": len(removed), "failed": failed}})
        if not removed:
            logger.error("Calendar delete failed for user_id=%s: %s", composio_user_id, last_error)
            hint = f" (details: {last_error})" if last_error else ""
            writer({"kind": "say", "text": "I couldn't remove those events. Google Calendar may "
                    f"not be connected for {composio_user_id} — check Settings and retry.{hint}"})
            return {}  # keep pending for retry
        session_tools.set_pending_action(session_id, None)
        sim = " (simulated — add a Composio key to remove them for real)" if sim_any else ""
        names = ", ".join(f"“{n}”" for n in removed)
        tail = f" ({failed} couldn't be removed)" if failed else ""
        writer({"kind": "say", "text": f"Removed {names} from your calendar{sim}{tail}."})
        return {}

    # Unknown / stale pending action.
    session_tools.set_pending_action(session_id, None)
    writer({"kind": "say", "text": "That request expired — could you tell me again what you'd "
            "like to do?"})
    return {}
