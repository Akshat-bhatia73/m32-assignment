"""Shared conversation helpers used across graph nodes and the streamer."""

from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = (
    "You are [Meeting]32, a calm, plain-spoken operations copilot for busy small-business "
    "owners and department heads. Keep replies short, concrete, and free of jargon. You help "
    "turn meeting notes into tracked action items, follow-up emails, and calendar events, and "
    "you remember what the user tells you within this conversation."
)


def system_prompt(user_name: str | None = None) -> str:
    """Base system prompt, optionally personalized with the signed-in user's name."""
    if user_name:
        return (
            f"{SYSTEM_PROMPT} The user's name is {user_name}; address them naturally by name "
            "when it feels warm and appropriate (don't overdo it)."
        )
    return SYSTEM_PROMPT


_TITLE_SYSTEM = (
    "Write a short title (3-6 words, Title Case) summarizing what this meeting note or message "
    "is about. No quotes, no trailing punctuation, no leading 'Re:' or 'Title:'. Just the title."
)


async def generate_title(text: str) -> str:
    """A concise, human-readable session title derived from the first user turn.

    Falls back to a trimmed snippet when no LLM is configured or the call fails, so a session
    always gets a usable title.
    """
    from app.llm.provider import get_llm, has_llm

    snippet = " ".join(text.split())
    fallback = (snippet[:57].rstrip() + "…") if len(snippet) > 60 else (snippet or "New session")
    if not has_llm():
        return fallback
    try:
        llm = get_llm(temperature=0.0)
        ai = await llm.ainvoke(
            [SystemMessage(content=_TITLE_SYSTEM), HumanMessage(content=text[:1200])]
        )
        title = extract_text(ai.content).strip().strip('"').strip()
        return title[:80] or fallback
    except Exception:
        return fallback


def extract_text(content: object) -> str:
    """Pull plain text from a LangChain message chunk.

    Gemini 3.x streams content as a list of typed blocks
    (e.g. ``[{"type": "text", "text": "..."}]``); older models / OpenAI use a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""
