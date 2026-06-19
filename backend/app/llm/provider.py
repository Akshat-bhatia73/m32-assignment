"""LLM provider wrapper.

Two tiers, both built here so callers stay provider-agnostic:

* ``get_llm`` — the **user-selected** conversation model (chat, summary, email voice). The active
  selection is carried per-request in a context variable set by the chat handler.
* ``get_classifier_llm`` — a **fixed, economical** model for internal classification / parsing
  (routing, yes/no confirmation, intent + reschedule/cancel parsing, extraction, titles). Pinning
  these high-frequency calls to a cheap model keeps cost down regardless of the user's pick.

Reasoning models (GPT-5.5) reject a custom temperature and take a ``reasoning_effort`` instead;
that difference is handled here from each model's ``ModelSpec``.
"""

import contextvars
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.llm.models import (
    BY_ID,
    CATALOG,
    CLASSIFIER_GOOGLE,
    CLASSIFIER_OPENAI,
    FALLBACK_DEFAULT_GOOGLE,
    PREFERRED_DEFAULT_OPENAI,
    ModelSpec,
)


@dataclass(frozen=True)
class Selection:
    """A resolved conversation-model choice: a catalog id plus optional reasoning effort."""

    model_id: str
    reasoning: str | None = None


def _has_key(provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    return bool(settings.gemini_api_key)


def has_llm() -> bool:
    """True when any provider key is configured (the agent can run at all)."""
    return bool(settings.openai_api_key or settings.gemini_api_key)


def available_models() -> list[ModelSpec]:
    """Catalog entries whose provider has an API key configured."""
    return [m for m in CATALOG if _has_key(m.provider)]


def default_selection() -> Selection:
    """The default conversation model — GPT-5.5 (low) when OpenAI is available, else Gemini."""
    if _has_key("openai") and PREFERRED_DEFAULT_OPENAI in BY_ID:
        spec = BY_ID[PREFERRED_DEFAULT_OPENAI]
        return Selection(spec.id, spec.default_reasoning)
    if _has_key("google") and FALLBACK_DEFAULT_GOOGLE in BY_ID:
        return Selection(FALLBACK_DEFAULT_GOOGLE)
    avail = available_models()
    if avail:
        return Selection(avail[0].id, avail[0].default_reasoning)
    return Selection(FALLBACK_DEFAULT_GOOGLE)  # nothing configured; has_llm() gates real use


def resolve_selection(model_id: str | None, reasoning: str | None) -> Selection:
    """Validate a requested (model, reasoning) pair, falling back to the default when invalid
    or when the requested model's provider has no key."""
    spec = BY_ID.get(model_id or "")
    if spec is None or not _has_key(spec.provider):
        return default_selection()
    if spec.supports_reasoning:
        effort = reasoning if reasoning in spec.reasoning_options else spec.default_reasoning
        return Selection(spec.id, effort)
    return Selection(spec.id)


# Per-request active selection. Defaults to None so any code path that didn't set one (e.g. the
# title helper, which only uses the classifier anyway) still resolves to the global default.
_active: contextvars.ContextVar[Selection | None] = contextvars.ContextVar(
    "active_model", default=None
)


def set_active_model(model_id: str | None, reasoning: str | None = None) -> Selection:
    """Set the conversation model for the current request context and return what was resolved."""
    sel = resolve_selection(model_id, reasoning)
    _active.set(sel)
    return sel


def _current() -> Selection:
    return _active.get() or default_selection()


@lru_cache(maxsize=64)
def _build(model_id: str, reasoning: str | None, temperature: float) -> BaseChatModel:
    """Construct (and cache) a LangChain chat model for a concrete configuration."""
    spec = BY_ID[model_id]
    if spec.provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict = {"model": spec.id, "api_key": settings.openai_api_key}
        if spec.supports_temperature:
            kwargs["temperature"] = temperature
        if spec.supports_reasoning and reasoning:
            kwargs["reasoning_effort"] = reasoning
        return ChatOpenAI(**kwargs)

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=spec.id,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
    )


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """The user-selected conversation model (chat / summary / email voice).

    ``temperature`` is honored for models that support it and ignored for reasoning models.
    """
    sel = _current()
    spec = BY_ID[sel.model_id]
    # Reasoning models reject a custom temperature; pass a fixed placeholder that _build drops.
    temp = temperature if spec.supports_temperature else 1.0
    return _build(sel.model_id, sel.reasoning, temp)


@lru_cache(maxsize=1)
def _classifier_id() -> str:
    return CLASSIFIER_OPENAI if _has_key("openai") else CLASSIFIER_GOOGLE


def get_classifier_llm(temperature: float = 0.0) -> BaseChatModel:
    """Fixed, economical model for internal classification / parsing (cost optimization)."""
    return _build(_classifier_id(), None, temperature)
