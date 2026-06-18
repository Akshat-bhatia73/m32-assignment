"""Comms node — drafts a follow-up email or proposes calendar events, then asks to confirm.

Nothing external happens here. It prepares the action, stores it as the session's pending action,
and streams a plain-language draft + a confirmation prompt. The confirm node executes on "yes".
"""

import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.agents.tools import board_tools, session_tools

_SCHEDULE_HINTS = ("schedul", "calendar", "event", "invite", "block time", "add to my cal")

EMAIL_SYSTEM = (
    "You draft a short, warm, professional follow-up email for a small-business owner, summarizing "
    "the meeting's action items. Plain language, no jargon. Provide a concise subject line and a "
    "body that lists who owns what and any due dates. Keep it under ~150 words."
)


class EmailDraft(BaseModel):
    subject: str = Field(description="Concise subject line.")
    body: str = Field(description="Email body, plain text.")


def _wants_schedule(message: str) -> bool:
    low = message.lower()
    return any(h in low for h in _SCHEDULE_HINTS)


async def comms_node(state: GraphState) -> dict:
    from app.llm.provider import get_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    message = extract_text(state["messages"][-1].content)
    open_items = board_tools.list_items(session_id, open_only=True)

    if _wants_schedule(message):
        tool_call_id = uuid.uuid4().hex
        writer(
            {
                "kind": "tool_input",
                "tool_call_id": tool_call_id,
                "tool_name": "plan_calendar_events",
                "input": {"open_items": len(open_items)},
            }
        )
        dated = [i for i in open_items if i.get("due_date")]
        if not dated:
            writer({"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"events": 0}})
            writer(
                {"kind": "say", "text": "None of your open items have a due date yet, so there's "
                 "nothing to schedule. Add due dates and I'll set up the calendar events."}
            )
            session_tools.set_pending_action(session_id, None)
            return {}
        events = [
            {"action_item_id": i["id"], "summary": i["task"], "date": i["due_date"]}
            for i in dated
        ]
        writer(
            {"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"events": len(events)}}
        )
        session_tools.set_pending_action(
            session_id, {"type": "create_events", "events": events}
        )
        lines = "\n".join(f"• {e['summary']} — {e['date']}" for e in events)
        writer(
            {"kind": "say", "text": f"I can add {len(events)} calendar event"
             f"{'s' if len(events) != 1 else ''}:\n{lines}\n\nReply “yes” to add them, "
             "or tell me what to change."}
        )
        return {}

    # Email follow-up
    if not open_items:
        writer({"kind": "say", "text": "There are no open action items to summarize yet."})
        return {}

    tool_call_id = uuid.uuid4().hex
    writer(
        {
            "kind": "tool_input",
            "tool_call_id": tool_call_id,
            "tool_name": "draft_followup_email",
            "input": {"items": len(open_items)},
        }
    )

    llm = get_llm(temperature=0.4).with_structured_output(EmailDraft)
    item_lines = "\n".join(
        f"- {i['task']}"
        + (f" (owner: {i['owner']})" if i.get("owner") else "")
        + (f", due {i['due_date']}" if i.get("due_date") else "")
        for i in open_items
    )
    draft: EmailDraft = await llm.ainvoke(
        [
            SystemMessage(content=EMAIL_SYSTEM),
            HumanMessage(content=f"Action items:\n{item_lines}"),
        ]
    )
    writer(
        {"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"subject": draft.subject}}
    )
    # Send the summary to the owner themselves (a real, valid inbox); the body covers who-owns-what.
    recipient = state.get("user_email")
    if not recipient:
        writer({"kind": "say", "text": "I don't have an email address on file to send this to."})
        return {}
    to = [recipient]
    session_tools.set_pending_action(
        session_id,
        {"type": "send_email", "to": to, "subject": draft.subject, "body": draft.body},
    )
    # Structured part → the client renders an editable email card with a "Send" action.
    writer({"kind": "email_draft", "to": to, "subject": draft.subject, "body": draft.body})
    # Plain-text twin: persisted for history and shown as a graceful fallback on reload
    # (when the data part isn't replayed). The client hides it while the card is present.
    writer(
        {"kind": "say", "text": "Here's a draft follow-up:\n\n"
         f"To: {', '.join(to)}\nSubject: {draft.subject}\n\n{draft.body}\n\n"
         "Reply “yes” to send it, or tell me what to change."}
    )
    return {}
