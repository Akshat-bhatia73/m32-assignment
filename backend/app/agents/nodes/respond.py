"""Respond node — general chat with in-session memory (Phase 1 behavior).

Tokens stream via LangGraph's "messages" mode.
"""

from langchain_core.messages import SystemMessage

from app.agents.conversation import system_prompt
from app.agents.state import GraphState
from app.llm.provider import get_llm


async def respond_node(state: GraphState) -> dict:
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt(state.get("user_name"))),
        *state["messages"],
    ]
    ai = await llm.ainvoke(messages)
    return {"messages": [ai]}
