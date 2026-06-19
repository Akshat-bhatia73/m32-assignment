"""Summarize node — streams a short plain-language confirmation after extraction.

Tokens stream to the client via LangGraph's "messages" stream mode (the streamer filters on the
node name), so the assistant "speaks" while the board fills in.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import GraphState
from app.llm.provider import get_llm

SUMMARY_SYSTEM = (
    "You are [Meeting]32. Present the supplied meeting summary first under 'Summary'. Then, if "
    "there are proposed action items, show them under 'Proposed action items' as a concise list "
    "including only supplied owners and dates, and ask whether to add them to the board. Make it "
    "explicit that nothing has been added yet. If there are no items, say no clear action items "
    "were found. Never invent or rename details."
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
    context = (
        f"Meeting summary:\n{state.get('meeting_summary') or 'No summary available.'}\n\n"
        f"Proposed action items:\n{_format_items(extracted)}"
    )
    ai = await llm.ainvoke(
        [SystemMessage(content=SUMMARY_SYSTEM), HumanMessage(content=context)]
    )
    return {"messages": [ai]}
