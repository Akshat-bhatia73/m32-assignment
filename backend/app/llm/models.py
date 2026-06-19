"""Model catalog — the single source of truth for which LLMs the app can use.

This replaces hardcoded model names in the env. The user picks a *conversation* model from this
catalog (chat / summary / email voice); cheap internal classification and parsing is pinned to a
fixed economical model (see ``provider.py``). Each spec also records how the model must be called
(``temperature`` vs. ``reasoning_effort``) so the provider wrapper can configure it correctly.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str  # the API model id passed to the provider SDK
    label: str  # display name in the UI
    provider: str  # "openai" | "google" — also selects which API key is required
    blurb: str  # one-line description shown in the model picker
    # Relative running cost, shown as 1–N "$" in the picker (1 = cheapest).
    cost_tier: int = 1
    # Reasoning models (e.g. GPT-5.5) reject a custom temperature and take a reasoning effort.
    supports_temperature: bool = True
    supports_reasoning: bool = False
    reasoning_options: tuple[str, ...] = ()
    default_reasoning: str | None = None


# Order here is the order shown in the picker (within each provider group).
CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="gpt-5.5",
        label="GPT-5.5",
        provider="openai",
        blurb="OpenAI's flagship. Deliberate, reasoning-driven answers.",
        cost_tier=2,
        supports_temperature=False,
        supports_reasoning=True,
        reasoning_options=("low", "medium", "high"),
        default_reasoning="low",
    ),
    ModelSpec(
        id="gpt-5.4-mini",
        label="GPT-5.4 Mini",
        provider="openai",
        blurb="Fast, low-cost OpenAI model. Also powers the agent's internal steps.",
    ),
    ModelSpec(
        id="gemini-3.1-flash-lite",
        label="Gemini 3.1 Flash Lite",
        provider="google",
        blurb="Google's quick, economical model. A solid everyday default.",
    ),
    ModelSpec(
        id="gemma-4-31b-it",
        label="Gemma 4 31B",
        provider="google",
        blurb="Google's open-weight Gemma. Lightweight and capable.",
    ),
)

BY_ID: dict[str, ModelSpec] = {m.id: m for m in CATALOG}

# Highest cost tier in the catalog — the picker renders cost as filled/faded "$" up to this.
MAX_COST_TIER = max(m.cost_tier for m in CATALOG)

# Internal classification / parsing always uses the cheapest capable model, regardless of the
# user's conversation pick — OpenAI's mini first, Google's flash-lite when no OpenAI key is set.
CLASSIFIER_OPENAI = "gpt-5.4-mini"
CLASSIFIER_GOOGLE = "gemini-3.1-flash-lite"

# Preferred conversation default when its provider key is present; Google fallback otherwise.
PREFERRED_DEFAULT_OPENAI = "gpt-5.5"
FALLBACK_DEFAULT_GOOGLE = "gemini-3.1-flash-lite"

PROVIDER_LABELS = {"openai": "OpenAI", "google": "Google"}
