"""Summarize node — streams a short plain-language confirmation after extraction.

Tokens stream to the client via LangGraph's "messages" stream mode (the streamer filters on the
node name), so the assistant "speaks" while the board fills in.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import GraphState
from app.llm.provider import get_llm

SUMMARY_SYSTEM = (
    "You are [Meeting]32. You just added action items to the user's board from their notes. "
    "Confirm in 1-2 short, warm, plain sentences: say how many items you captured and mention a "
    "couple by name. If there were none, say you couldn't find clear action items and invite them "
    "to share more detail. No bullet lists, no jargon."
)


def _format_items(extracted: list[dict]) -> str:
    if not extracted:
        return "No action items were extracted."
    lines = []
    for it in extracted:
        owner = f" (owner: {it['owner']})" if it.get("owner") else ""
        due = f" due {it['due_date']}" if it.get("due_date") else ""
        lines.append(f"- {it['task']}{owner}{due}")
    return "\n".join(lines)


async def summarize_node(state: GraphState) -> dict:
    extracted = state.get("extracted", [])
    llm = get_llm(temperature=0.3)
    context = f"Items added to the board:\n{_format_items(extracted)}"
    ai = await llm.ainvoke(
        [SystemMessage(content=SUMMARY_SYSTEM), HumanMessage(content=context)]
    )
    return {"messages": [ai]}
