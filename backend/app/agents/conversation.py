"""Shared conversation helpers used across graph nodes and the streamer."""

SYSTEM_PROMPT = (
    "You are Meeting → Done, a calm, plain-spoken operations copilot for busy small-business "
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
