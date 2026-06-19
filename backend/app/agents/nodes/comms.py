"""Comms node — drafts a follow-up email or proposes calendar events, then asks to confirm.

Nothing external happens here. It prepares the action, stores it as the session's pending action,
and streams a plain-language draft + a confirmation prompt. The confirm node executes on "yes".
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.people import resolve_owner_emails as _resolve_owner_emails
from app.agents.state import GraphState
from app.agents.tools import board_tools, composio_tools, session_tools
from app.config import settings

_SCHEDULE_HINTS = ("schedul", "calendar", "event", "invite", "block time", "add to my cal")

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
    "You draft a short, warm, professional follow-up email for a small-business owner, summarizing "
    "the meeting's action items. Plain language, no jargon.\n\n"
    "Return a concise subject line and a plain-text body. Format the body EXACTLY like this, using "
    "real newline characters (\\n) — never run the list together on one line:\n"
    "Hi team,\n\n"
    "<one short intro sentence>\n\n"
    "- <action item> — <Owner>, due <date>\n"
    "- <next action item> — <Owner>, due <date>\n\n"
    "<one short closing sentence>\n\n"
    "Thanks,\n"
    "<sender name>\n\n"
    "Rules: put each action item on its OWN line starting with '- '. Omit 'due <date>' when there "
    "is no due date, and omit the owner when none is given. Sign off with 'Thanks,' on its own "
    "line followed by the sender's name on the next line. Keep the whole body under ~150 words.\n"
    "Summarize ONLY the action items provided — do not invent or add tasks, people, dates, "
    "numbers, decisions, or commitments that are not in the list."
)


class EmailDraft(BaseModel):
    subject: str = Field(description="Concise subject line.")
    body: str = Field(
        description="Email body as plain text with real newlines; each action item on its own "
        "line, signed off with the sender's name."
    )


def _wants_schedule(message: str) -> bool:
    low = message.lower()
    return any(h in low for h in _SCHEDULE_HINTS)


_RESCHEDULE_HINTS = ("reschedul", "move the", "move my", "push back", "push the", "shift the",
                     "change the time", "move it", "bump the", "rename the", "retitle",
                     "change the title", "change the name")

_CANCEL_HINTS = ("cancel", "delete", "remove", "call off", "drop the", "take off",
                 "get rid of", "clear the")
_EVENT_WORDS = ("event", "meeting", "calendar", "invite", "appointment", "booking")


def _wants_reschedule(message: str) -> bool:
    low = message.lower()
    return any(h in low for h in _RESCHEDULE_HINTS)


def _wants_cancel_event(message: str) -> bool:
    """True for 'cancel/remove the calendar event' style requests (not 'remove a task')."""
    low = message.lower()
    return any(h in low for h in _CANCEL_HINTS) and any(w in low for w in _EVENT_WORDS)


# Calendar-view phrasings ("what's on my calendar"), guarded against creation requests so
# "add this to my calendar" still schedules instead of just listing.
_VIEW_HINTS = ("what's on my", "whats on my", "what is on my", "what events", "what meetings",
               "what do i have", "what's coming up", "whats coming up", "show me my",
               "show my", "my schedule", "my agenda", "list my event", "any events",
               "events today", "events for today", "on my calendar", "check my calendar",
               "view my calendar", "see my calendar", "look at my calendar")
_VIEW_GUARD = ("schedul", "add ", "create", "set up", "block ", "book ", "put ")


def _wants_calendar_view(message: str) -> bool:
    low = message.lower()
    if any(g in low for g in _VIEW_GUARD):
        return False
    return any(h in low for h in _VIEW_HINTS)


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
    from app.llm.provider import get_llm

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
    llm = get_llm(temperature=0.0).with_structured_output(RescheduleParse)
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
    from app.llm.provider import get_llm

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
    llm = get_llm(temperature=0.0).with_structured_output(CancelParse)
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


async def comms_node(state: GraphState) -> dict:
    from app.llm.provider import get_llm

    writer = get_stream_writer()
    session_id = state["session_id"]
    message = extract_text(state["messages"][-1].content)
    open_items = board_tools.list_items(session_id, open_only=True)

    if _wants_cancel_event(message):
        return await _cancel_event(state, message)

    if _wants_reschedule(message):
        return await _reschedule(state, message)

    if _wants_calendar_view(message):
        return await _calendar_view(state, message)

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
            start = datetime.combine(
                date.fromisoformat(e["date"]), time(_EVENT_HOUR, 0), tz
            )
            e["start"] = start.isoformat()
            e["conflict"] = _conflict_for(e["date"], intervals)

        writer(
            {"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"events": len(events)}}
        )
        session_tools.set_pending_action(
            session_id, {"type": "create_events", "events": events}
        )
        # Structured part → the client renders a calendar proposal card with ⚠ conflict badges.
        writer(
            {"kind": "calendar_proposal", "events": [
                {"summary": e["summary"], "date": e["date"], "start": e["start"],
                 "conflict": e["conflict"]}
                for e in events
            ]}
        )
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
        writer(
            {"kind": "say", "text": f"I can add {len(events)} calendar event"
             f"{'s' if len(events) != 1 else ''}:\n{lines}{warn}\n\nApprove below to add them, "
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
    # Sign the email with the sender's real name (fall back to the email's local part).
    sender = state.get("user_name") or (
        (state.get("user_email") or "").split("@")[0] or "The team"
    )
    draft: EmailDraft = await llm.ainvoke(
        [
            SystemMessage(content=EMAIL_SYSTEM),
            HumanMessage(
                content=f"Sender name (use in the sign-off): {sender}\n\n"
                f"Action items:\n{item_lines}"
            ),
        ]
    )
    writer(
        {"kind": "tool_output", "tool_call_id": tool_call_id, "output": {"subject": draft.subject}}
    )
    organizer = state.get("user_email")
    if not organizer:
        writer({"kind": "say", "text": "I don't have an email address on file to send this to."})
        return {}
    # Resolve each item's owner to a real teammate email; the follow-up goes to the owners
    # (with the organizer always included), not just the sender's own inbox.
    members = state.get("members") or []
    owner_emails = _resolve_owner_emails(open_items, members)
    to = sorted(owner_emails | {organizer})
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
         "Use the buttons below to send it, or tell me what to change."}
    )
    return {}
