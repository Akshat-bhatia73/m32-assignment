"""Comms node — drafts a follow-up email or proposes calendar events, then asks to confirm.

Nothing external happens here. It prepares the action, stores it as the session's pending action,
and streams a plain-language draft + a confirmation prompt. The confirm node executes on "yes".
"""

import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.people import resolve_owner_emails as _resolve_owner_emails
from app.agents.state import GraphState
from app.agents.tools import board_tools, composio_tools, session_tools
from app.config import settings

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Proposed events default to a 9:00, 30-minute block (mirrors create_calendar_event).
_EVENT_HOUR = 9
_EVENT_DURATION_MIN = 30


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.composio_timezone)
    except Exception:  # noqa: BLE001 — bad/unknown tz string falls back to UTC
        return ZoneInfo("UTC")


def _existing_intervals(events: list[dict]) -> list[tuple[datetime, datetime, str]]:
    """Normalize listed calendar events into (start_utc, end_utc, summary) busy intervals."""
    tz = _tz()
    out: list[tuple[datetime, datetime, str]] = []
    for e in events:
        summary = e.get("summary") or "(busy)"
        start_raw, end_raw = e.get("start"), e.get("end")
        if not start_raw:
            continue
        try:
            if e.get("all_day"):
                # Date-only bounds; treat as busy for the whole local day(s).
                s = datetime.combine(date.fromisoformat(start_raw), time.min, tz)
                end_date = (
                    date.fromisoformat(end_raw) if end_raw else s.date() + timedelta(days=1)
                )
                en = datetime.combine(end_date, time.min, tz)
            else:
                s = datetime.fromisoformat(start_raw)
                en = datetime.fromisoformat(end_raw) if end_raw else s + timedelta(minutes=30)
        except ValueError:
            continue
        # Make tz-aware (assume configured tz if the source had no offset), then compare in UTC.
        s = s.replace(tzinfo=tz) if s.tzinfo is None else s
        en = en.replace(tzinfo=tz) if en.tzinfo is None else en
        out.append((s.astimezone(UTC), en.astimezone(UTC), summary))
    return out


def _conflict_for(event_date: str, intervals: list[tuple[datetime, datetime, str]]) -> str | None:
    """Return the summary of an existing event the proposed 9:00 block collides with, if any."""
    try:
        d = date.fromisoformat(event_date)
    except (ValueError, TypeError):
        return None
    tz = _tz()
    start = datetime.combine(d, time(_EVENT_HOUR, 0), tz).astimezone(UTC)
    end = start + timedelta(minutes=_EVENT_DURATION_MIN)
    for s, en, summary in intervals:
        if start < en and s < end:  # half-open interval overlap
            return summary
    return None

EMAIL_SYSTEM = (
    "You draft a short, warm, professional email on the user's behalf. Plain language, no jargon. "
    "Write the email the user actually asked for: if it's a meeting follow-up, summarize the "
    "action items provided; otherwise write about whatever they described.\n\n"
    "Return a concise subject line and a plain-text body using real newline characters (\\n). "
    "Structure it as:\n"
    "<greeting>\n\n"
    "<short intro / purpose>\n\n"
    "<body — if you list tasks or points, put each on its OWN line starting with '- '>\n\n"
    "<short closing>\n\n"
    "Thanks,\n"
    "<sender name>\n\n"
    "Rules: never run a list together on one line. Sign off with 'Thanks,' on its own line then "
    "the sender's name on the next line. Keep the body under ~150 words. Use ONLY facts the user "
    "gave (in their request or the conversation) and the action items provided — do NOT invent "
    "recipient names, dates, numbers, decisions, or commitments."
)


class EmailDraft(BaseModel):
    subject: str = Field(description="Concise subject line.")
    body: str = Field(
        description="Email body as plain text with real newlines; any list on its own lines, "
        "signed off with the sender's name."
    )


class CommsIntent(BaseModel):
    intent: Literal["email", "schedule", "reschedule", "cancel", "calendar_view"]


async def _classify_comms(state: GraphState, message: str) -> str:
    """Pick the comms sub-intent with an LLM (robust to topic words like 'schedule' inside an
    email request) — replaces brittle keyword matching."""
    from app.llm.provider import get_classifier_llm

    llm = get_classifier_llm().with_structured_output(CommsIntent)
    res: CommsIntent = await llm.ainvoke([
        SystemMessage(content=(
            "Classify the user's request in an email + calendar assistant. Pick ONE intent based "
            "on the ACTION the user wants, NOT on topic words mentioned in passing:\n"
            "- 'email': write, draft, or send an email/message to someone — even if the email's "
            "topic happens to mention scheduling, meetings, or events.\n"
            "- 'schedule': add the user's existing action items / tasks to their calendar.\n"
            "- 'reschedule': move, rename, or change the time of an existing calendar event.\n"
            "- 'cancel': delete or remove existing calendar events.\n"
            "- 'calendar_view': look at, list, or check what's on the user's calendar.\n"
            "Example: 'draft an email about whether to schedule a war room' → 'email' (the action "
            "is drafting an email)."
        )),
        HumanMessage(content=(
            f"Recent conversation:\n{_recent_context(state)}\n\nLatest request:\n{message}"
        )),
    ])
    return res.intent


class RescheduleParse(BaseModel):
    event_id: str | None = Field(
        default=None, description="The id of the calendar event to edit, or null if unclear."
    )
    new_datetime: str | None = Field(
        default=None,
        description="New start as ISO 8601 local datetime 'YYYY-MM-DDTHH:MM:SS', or null if the "
        "time isn't changing.",
    )
    new_title: str | None = Field(
        default=None,
        description="New event title if the user is renaming it, else null.",
    )


class CancelParse(BaseModel):
    event_ids: list[str] = Field(
        default_factory=list,
        description="ids of the calendar events the user wants removed (one or more).",
    )


def _view_window(message: str) -> tuple[int, int]:
    """(days_from_today, span_in_days) to scope a calendar read to the user's phrasing."""
    low = message.lower()
    if "tomorrow" in low:
        return (1, 1)
    if "today" in low or "tonight" in low:
        return (0, 1)
    if "week" in low:
        return (0, 7)
    return (0, 14)


def _list_user_events(state: GraphState, *, days_from: int = 0, days_span: int = 14) -> dict:
    """Fetch the user's REAL Google Calendar events from the start of the window onward."""
    user_email = state.get("user_email")
    if not user_email:
        return {"status": "error", "events": [], "error": "no_email"}
    tz = _tz()
    start = datetime.combine(
        datetime.now(tz).date() + timedelta(days=days_from), time.min, tz
    )
    end = start + timedelta(days=days_span)
    return composio_tools.list_calendar_events(
        user_id=user_email,
        time_min=start.astimezone(UTC).isoformat(),
        time_max=end.astimezone(UTC).isoformat(),
    )


def _event_roster(events: list[dict]) -> str:
    return "\n".join(
        f"- id={e['id']} | {e.get('summary') or '(no title)'} | starts {e.get('start') or 'n/a'}"
        for e in events
    )


def _recent_context(state: GraphState, limit: int = 6) -> str:
    """The last few turns as plain text, so the LLM can resolve references like 'these'/'those'
    to the events it most recently listed (proper conversational context)."""
    lines = []
    for m in state["messages"][-limit:]:
        text = extract_text(m.content).strip()
        if not text:
            continue
        role = "User" if isinstance(m, HumanMessage) else (
            "Assistant" if isinstance(m, AIMessage) else "")
        if role:
            lines.append(f"{role}: {text}")
    return "\n".join(lines) or "(no prior turns)"


def _email_recipients(
    message: str,
    members: list[dict],
    pending: dict | None,
    fallback: set[str],
) -> list[str]:
    """Resolve explicit addresses/names, or preserve the current draft recipients on revision."""
    explicit = {email.lower() for email in EMAIL_RE.findall(message)}
    if explicit:
        return sorted(explicit)
    words = set(re.findall(r"[a-z]+", message.lower()))
    named = {
        member["email"].lower()
        for member in members
        if member.get("email")
        and set(re.findall(r"[a-z]+", (member.get("name") or "").lower())) & words
    }
    if named:
        return sorted(named)
    if pending and pending.get("type") == "send_email" and pending.get("to"):
        return sorted({email.lower() for email in pending["to"]})
    return sorted(fallback)


def _board_ref_map(session_id) -> dict[str, str]:
    """event_id -> board item id, for app-scheduled events (so we can reopen the task on delete)."""
    return {
        i["external_ref"]: i["id"]
        for i in board_tools.list_items(session_id)
        if i.get("external_ref")
    }


def _event_start_local(e: dict) -> str | None:
    """The event's existing start as a tz-naive 'YYYY-MM-DDTHH:MM:SS' (for title-only edits)."""
    raw = e.get("start")
    if not raw:
        return None
    try:
        if e.get("all_day"):
            return f"{date.fromisoformat(raw).isoformat()}T{_EVENT_HOUR:02d}:00:00"
        return datetime.fromisoformat(raw).strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _fmt_event_line(e: dict) -> str:
    raw = e.get("start")
    label = raw or ""
    try:
        if raw and e.get("all_day"):
            label = date.fromisoformat(raw).strftime("%a %b %d (all day)")
        elif raw:
            label = datetime.fromisoformat(raw).strftime("%a %b %d, %I:%M %p")
    except ValueError:
        pass
    title = e.get("summary") or "(no title)"
    return f"• {title} — {label}" if label else f"• {title}"


def _calendar_unavailable(writer, status: str, error: str | None) -> bool:
    """Emit a grounded 'can't read your calendar' message; return True if we handled it."""
    if status == "error" and error == "no_email":
        writer({"kind": "say", "text": "I don't have your email on file to read your calendar."})
        return True
    if status == "simulated":
        writer({"kind": "say", "text": "Your Google Calendar isn't connected yet, so I can't see "
                "your real events. Connect it in Settings and I'll pull them up."})
        return True
    if status != "ok":
        writer({"kind": "say", "text": "I couldn't reach your calendar just now — check that "
                "Google Calendar is connected in Settings and try again."})
        return True
    return False


async def _calendar_view(state: GraphState, message: str) -> dict:
    """Answer a question about the calendar from the user's REAL events — never invented ones."""
    writer = get_stream_writer()
    days_from, days_span = _view_window(message)
    tool_call_id = uuid.uuid4().hex
    writer({"kind": "tool_input", "tool_call_id": tool_call_id,
            "tool_name": "list_calendar_events", "input": {"days": days_span}})
    res = _list_user_events(state, days_from=days_from, days_span=days_span)
    events = res.get("events", [])
    writer({"kind": "tool_output", "tool_call_id": tool_call_id,
            "output": {"events": len(events), "status": res.get("status")}})
    if _calendar_unavailable(writer, res.get("status"), res.get("error")):
        return {}
    if not events:
        scope = "today" if days_span == 1 else "coming up"
        writer({"kind": "say", "text": f"You have no events {scope} on your calendar."})
        return {}
    lines = "\n".join(_fmt_event_line(e) for e in events)
    writer({"kind": "say", "text": f"Here's what's on your calendar:\n{lines}\n\nWant me to "
            "reschedule or remove any of these?"})
    return {}


async def _reschedule(state: GraphState, message: str) -> dict:
    """Match a move/rename request to a REAL calendar event and queue the edit."""
    from app.llm.provider import get_classifier_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    res = _list_user_events(state)
    if _calendar_unavailable(writer, res.get("status"), res.get("error")):
        return {}
    events = res.get("events", [])
    if not events:
        writer({"kind": "say", "text": "I don't see any upcoming events to change."})
        return {}

    today = datetime.now(_tz()).date().isoformat()
    llm = get_classifier_llm().with_structured_output(RescheduleParse)
    parsed: RescheduleParse = await llm.ainvoke([
        SystemMessage(content=(
            "Match the user's request to one of their calendar events and resolve any changes to "
            f"its start time and/or title. Today is {today}. Use the configured timezone. Vague "
            "times: morning=09:00, afternoon=14:00, evening=18:00. Use the recent conversation to "
            "resolve references like 'it', 'that meeting', or 'the one you mentioned' to the right "
            "event. Return the event's id, an ISO local datetime 'YYYY-MM-DDTHH:MM:SS' if the time "
            "changes (else null), and a new_title if renaming (else null). If you can't tell which "
            "event, return null event_id."
        )),
        HumanMessage(content=(
            f"Recent conversation:\n{_recent_context(state)}\n\n"
            f"EVENTS (id | title | start):\n{_event_roster(events)}\n\n"
            f"Latest request:\n{message}"
        )),
    ])
    target = next((e for e in events if e["id"] == parsed.event_id), None)
    if not target or (not parsed.new_datetime and not parsed.new_title):
        writer({"kind": "say", "text": "I'm not sure which event to change or what to change. Try "
                "e.g. “move the client call to tomorrow afternoon”."})
        return {}

    start_dt = parsed.new_datetime or _event_start_local(target)
    if not start_dt:
        writer({"kind": "say", "text": "I couldn't work out the event's time. Tell me a date/time "
                "and I'll update it."})
        return {}
    new_summary = parsed.new_title or (target.get("summary") or "(no title)")
    session_tools.set_pending_action(session_id, {
        "type": "reschedule_event",
        "action_item_id": _board_ref_map(session_id).get(target["id"]),
        "event_id": target["id"],
        "summary": new_summary,
        "start_datetime": start_dt,
    })
    when = start_dt.replace("T", " at ")
    change = []
    if parsed.new_title:
        change.append(f"rename it to “{parsed.new_title}”")
    if parsed.new_datetime:
        change.append(f"move it to {when}")
    detail = " and ".join(change) if change else f"update it ({when})"
    writer({"kind": "calendar_action", "action": "reschedule_event", "title": new_summary,
            "when": when, "detail": f"I'll {detail}."})
    writer({"kind": "say", "text": f"I'll {detail}. Approve to update your calendar, or tell me a "
            "different change."})
    return {}


async def _cancel_event(state: GraphState, message: str) -> dict:
    """Match a cancel/remove request to REAL calendar events and queue their deletion.

    Resolves references in context: 'delete all these' after listing *today's* events means
    today's events — not every event in the fetch window.
    """
    from app.llm.provider import get_classifier_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    # Fetch a wide candidate pool; the LLM scopes it using the conversation + request, so the
    # window heuristic can't over-select (the bug where "these" deleted future events too).
    res = _list_user_events(state, days_from=0, days_span=30)
    if _calendar_unavailable(writer, res.get("status"), res.get("error")):
        return {}
    events = res.get("events", [])
    if not events:
        writer({"kind": "say", "text": "I don't see any upcoming events to remove."})
        return {}

    today = datetime.now(_tz()).date().isoformat()
    llm = get_classifier_llm().with_structured_output(CancelParse)
    parsed: CancelParse = await llm.ainvoke([
        SystemMessage(content=(
            f"Decide which calendar events the user wants removed. Today is {today}.\n"
            "Use the recent conversation to resolve references — 'these', 'those', 'all of "
            "them', 'the ones you listed' mean the events you MOST RECENTLY showed the user, "
            "NOT every event in the list. Scope precisely:\n"
            "- a specific event they name → just that one\n"
            "- 'these' / 'all these' right after you listed today's events → only today's events\n"
            "- 'today's events' → only events dated today; 'tomorrow's' → only tomorrow's\n"
            "- 'everything on my calendar' / 'all my events' → every event listed\n"
            "Return ONLY ids from the EVENTS list for events the user actually referred to. If "
            "you genuinely can't tell, return an empty list."
        )),
        HumanMessage(content=(
            f"Recent conversation:\n{_recent_context(state)}\n\n"
            f"EVENTS (id | title | start):\n{_event_roster(events)}\n\n"
            f"Latest request:\n{message}"
        )),
    ])
    ids = set(parsed.event_ids)
    targets = [e for e in events if e["id"] in ids]
    if not targets:
        writer({"kind": "say", "text": "I'm not sure which event you mean. Tell me which one to "
                "remove, e.g. “cancel the client call”."})
        return {}

    refs = _board_ref_map(session_id)
    session_tools.set_pending_action(session_id, {
        "type": "delete_events",
        "events": [
            {"event_id": e["id"], "summary": e.get("summary") or "(no title)",
             "action_item_id": refs.get(e["id"])}
            for e in targets
        ],
    })
    names = ", ".join(f"“{e.get('summary') or '(no title)'}”" for e in targets)
    detail = f"Remove {names} from your calendar."
    if len(targets) == 1:
        title = targets[0].get("summary") or "(no title)"
    else:
        title = f"{len(targets)} events"
    writer({"kind": "calendar_action", "action": "delete_event", "title": title,
            "when": None, "detail": detail})
    writer({"kind": "say", "text": f"I'll remove {names} from your calendar. Approve to confirm, "
            "or decline to keep them."})
    return {}


async def _schedule_board(state: GraphState, message: str) -> dict:
    """Plan calendar events from the board's dated open items, flagging conflicts up front."""
    writer = get_stream_writer()
    session_id = state["session_id"]
    open_items = board_tools.list_items(session_id, open_only=True)

    tool_call_id = uuid.uuid4().hex
    writer({"kind": "tool_input", "tool_call_id": tool_call_id,
            "tool_name": "plan_calendar_events", "input": {"open_items": len(open_items)}})
    dated = [i for i in open_items if i.get("due_date")]
    if not dated:
        writer({"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"events": 0}})
        writer({"kind": "say", "text": "None of your open items have a due date yet, so there's "
                "nothing to schedule. Add due dates and I'll set up the calendar events."})
        session_tools.set_pending_action(session_id, None)
        return {}
    events = [
        {"action_item_id": i["id"], "summary": i["task"], "date": i["due_date"]} for i in dated
    ]
    # Read the user's existing agenda over the proposed window to flag overlaps up front.
    intervals: list[tuple[datetime, datetime, str]] = []
    user_email = state.get("user_email")
    dates = sorted(e["date"] for e in events)
    if user_email and dates:
        tz = _tz()
        time_min = datetime.combine(date.fromisoformat(dates[0]), time.min, tz)
        time_max = datetime.combine(
            date.fromisoformat(dates[-1]) + timedelta(days=1), time.min, tz
        )
        listed = composio_tools.list_calendar_events(
            user_id=user_email,
            time_min=time_min.astimezone(UTC).isoformat(),
            time_max=time_max.astimezone(UTC).isoformat(),
        )
        if listed.get("status") == "ok":
            intervals = _existing_intervals(listed.get("events", []))

    tz = _tz()
    for e in events:
        start = datetime.combine(date.fromisoformat(e["date"]), time(_EVENT_HOUR, 0), tz)
        e["start"] = start.isoformat()
        e["conflict"] = _conflict_for(e["date"], intervals)

    writer({"kind": "tool_output", "tool_call_id": tool_call_id,
            "output": {"events": len(events)}})
    session_tools.set_pending_action(session_id, {"type": "create_events", "events": events})
    # Structured part → the client renders a calendar proposal card with ⚠ conflict badges.
    writer({"kind": "calendar_proposal", "events": [
        {"summary": e["summary"], "date": e["date"], "start": e["start"], "conflict": e["conflict"]}
        for e in events
    ]})
    n_conflicts = sum(1 for e in events if e["conflict"])
    lines = "\n".join(
        f"• {e['summary']} — {e['date']} at {_EVENT_HOUR}:00"
        + (f" ⚠ overlaps “{e['conflict']}”" if e["conflict"] else "")
        for e in events
    )
    warn = (
        f"\n\n{n_conflicts} of these overlap an existing event — you can reschedule after, "
        "or tell me a different time."
        if n_conflicts
        else ""
    )
    writer({"kind": "say", "text": f"I can add {len(events)} calendar event"
            f"{'s' if len(events) != 1 else ''}:\n{lines}{warn}\n\nApprove below to add them, "
            "or tell me what to change."})
    return {}


async def _draft_email(state: GraphState, message: str) -> dict:
    """Draft ANY email the user asks for — a meeting follow-up or a custom message to a named
    recipient — then queue it for one-click send."""
    from app.llm.provider import get_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    # The meeting owner (session creator) is the sender — not whoever is currently viewing — so a
    # shared session always drafts with one consistent name + reply-to.
    organizer = state.get("organizer_email") or state.get("user_email")
    open_items = board_tools.list_items(session_id, open_only=True)
    members = state.get("members") or []

    tool_call_id = uuid.uuid4().hex
    writer({"kind": "tool_input", "tool_call_id": tool_call_id, "tool_name": "draft_email",
            "input": {"request": message[:200]}})

    sender = state.get("organizer_name") or ((organizer or "").split("@")[0] or "The team")
    item_lines = "\n".join(
        f"- {i['task']}"
        + (f" (owner: {i['owner']})" if i.get("owner") else "")
        + (f", due {i['due_date']}" if i.get("due_date") else "")
        for i in open_items
    ) or "(no action items on the board)"
    llm = get_llm(temperature=0.4).with_structured_output(EmailDraft)
    draft: EmailDraft = await llm.ainvoke([
        SystemMessage(content=EMAIL_SYSTEM),
        HumanMessage(content=(
            f"Sender name (use in the sign-off): {sender}\n\n"
            f"Write the email the user is asking for. Their request:\n{message}\n\n"
            f"Recent conversation (context):\n{_recent_context(state)}\n\n"
            f"Action items on the board (use ONLY if relevant to the request):\n{item_lines}"
        )),
    ])
    writer({"kind": "tool_output", "tool_call_id": tool_call_id,
            "output": {"subject": draft.subject}})

    # Recipients: an address the user named wins; otherwise fall back to item owners + the
    # organizer (the meeting-follow-up default).
    fallback = _resolve_owner_emails(open_items, members)
    if organizer:
        fallback = fallback | {organizer}
    to = _email_recipients(message, members, state.get("pending_action"), fallback)
    if not to:
        writer({"kind": "say", "text": "Who should I send this to? Tell me an email address and "
                "I'll draft it."})
        return {}

    session_tools.set_pending_action(
        session_id,
        {"type": "send_email", "to": to, "subject": draft.subject, "body": draft.body},
    )
    # Structured part → the client renders an editable email card with a "Send" action.
    writer({"kind": "email_draft", "to": to, "subject": draft.subject, "body": draft.body})
    # Plain-text twin: persisted for history, shown as a fallback on reload.
    writer({"kind": "say", "text": "Here's a draft:\n\n"
            f"To: {', '.join(to)}\nSubject: {draft.subject}\n\n{draft.body}\n\n"
            "Use the buttons below to send it, or tell me what to change."})
    return {}


# Dispatch table for the LLM-classified comms sub-intent.
_COMMS_HANDLERS = {
    "calendar_view": _calendar_view,
    "cancel": _cancel_event,
    "reschedule": _reschedule,
    "schedule": _schedule_board,
    "email": _draft_email,
}


async def comms_node(state: GraphState) -> dict:
    message = extract_text(state["messages"][-1].content)
    intent = await _classify_comms(state, message)
    handler = _COMMS_HANDLERS.get(intent, _draft_email)
    return await handler(state, message)
