"""Router node — classifies each user turn into a route."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.conversation import extract_text
from app.agents.state import GraphState
from app.llm.provider import get_llm

ROUTER_SYSTEM = (
    "You route a user's latest message in an operations-copilot chat. Choose:\n"
    "- 'extract': the message contains meeting notes, a transcript, or a request to pull out "
    "action items / tasks / to-dos / follow-ups from notes.\n"
    "- 'chat': anything else (greetings, questions, edits to existing items, general talk).\n"
    "Decide based only on the latest message."
)


class RouteDecision(BaseModel):
    route: Literal["extract", "chat"] = Field(description="Where to send this turn.")


async def router_node(state: GraphState) -> dict:
    last = extract_text(state["messages"][-1].content)
    llm = get_llm(temperature=0.0).with_structured_output(RouteDecision)
    decision: RouteDecision = await llm.ainvoke(
        [SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=last)]
    )
    return {"route": decision.route}
