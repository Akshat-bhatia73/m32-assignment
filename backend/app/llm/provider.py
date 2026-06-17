"""LLM provider wrapper.

Keep all model construction here so swapping Gemini <-> OpenAI is a one-line config change
(`LLM_PROVIDER`). Returns a LangChain chat model; callers stay provider-agnostic.
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def has_llm() -> bool:
    """True when an API key is configured for the selected provider."""
    if settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    return bool(settings.gemini_api_key)


@lru_cache
def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """Return the configured chat model. Raises if no key is set."""
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
    )
