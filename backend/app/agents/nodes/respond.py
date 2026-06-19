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


_GROUNDING = (
    "Answer questions about tasks / action items / owners / due dates / statuses ONLY from the "
    "ACTION BOARD above. If it's empty, or doesn't contain what they asked about, say so plainly. "
    "Never invent or guess tasks, owners, dates, statuses, calendar events, or emails. When you "
    "don't have the data, say you don't have it rather than making something up."
)


async def respond_node(state: GraphState) -> dict:
    llm = get_llm()
    grounding = SystemMessage(
        content=(
            f"{system_prompt(state.get('user_name'))}\n\n"
            f"{_board_context(state['session_id'])}\n\n{_GROUNDING}"
        )
    )
    ai = await llm.ainvoke([grounding, *state["messages"]])
    return {"messages": [ai]}
