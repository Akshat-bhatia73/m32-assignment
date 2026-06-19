"""Respond node — general chat, grounded in the session's real action board.

Tokens stream via LangGraph's "messages" mode. The board snapshot is injected so questions about
tasks/owners/due dates are answered from real data instead of being invented.
"""

from langchain_core.messages import SystemMessage

from app.agents.conversation import system_prompt
from app.agents.state import GraphState
from app.agents.tools import board_tools
from app.llm.provider import get_llm


def _board_context(session_id) -> str:
    """The current action board as plain text — the only task data the chat node may rely on."""
    items = board_tools.list_items(session_id)
    if not items:
        return "ACTION BOARD: empty (there are no action items in this workspace yet)."
    lines = []
    for i in items:
        owner = f", owner {i['owner']}" if i.get("owner") else ""
        due = f", due {i['due_date']}" if i.get("due_date") else ""
        lines.append(f"- {i['task']}{owner}{due} [{i['status']}]")
    return "ACTION BOARD (the ONLY task data you have — do not add to it):\n" + "\n".join(lines)


def _pending_context(pending: dict | None) -> str:
    """Expose the current proposal so conversational questions can be answered accurately."""
    if not pending:
        return "PENDING PROPOSAL: none."
    if pending.get("type") == "send_email":
        recipients = ", ".join(pending.get("to", [])) or "none"
        return (
            "PENDING EMAIL DRAFT (not sent):\n"
            f"- To: {recipients}\n"
            f"- Subject: {pending.get('subject') or '(no subject)'}"
        )
    return f"PENDING PROPOSAL (not executed): type={pending.get('type')}"


_GROUNDING = (
    "Answer questions about tasks / action items / owners / due dates / statuses ONLY from the "
    "ACTION BOARD above. If it's empty, or doesn't contain what they asked about, say so plainly. "
    "Never invent or guess tasks, owners, dates, statuses, calendar events, or emails. When you "
    "don't have the data, say you don't have it rather than making something up.\n\n"
    "A pending proposal is not approval. If the user questions or corrects a pending draft, "
    "answer the concern and explain the current proposal; never claim it was executed.\n\n"
    "You are answering, not acting. Do NOT draft emails, schedule events, or change the board in "
    "this reply. If the user asks what emails or calendar events should be set up (or for similar "
    "advice), suggest which board items look like they warrant a follow-up email or a calendar "
    "event, then offer to do it — e.g. 'Want me to draft those emails?' or 'Should I schedule "
    "these?' — and wait for them to say yes. Keep suggestions grounded in the board items above."
)


async def respond_node(state: GraphState) -> dict:
    llm = get_llm()
    grounding = SystemMessage(
        content=(
            f"{system_prompt(state.get('user_name'))}\n\n"
            f"{_board_context(state['session_id'])}\n\n"
            f"{_pending_context(state.get('pending_action'))}\n\n{_GROUNDING}"
        )
    )
    ai = await llm.ainvoke([grounding, *state["messages"]])
    return {"messages": [ai]}
