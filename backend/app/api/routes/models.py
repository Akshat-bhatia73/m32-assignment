"""Model catalog endpoint — lets the UI populate the model picker with the models that are
actually usable (i.e. whose provider has an API key configured) plus the server's default pick."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.llm.models import MAX_COST_TIER
from app.llm.provider import available_models, default_selection

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_models(current_user: CurrentUser) -> dict:
    default = default_selection()
    return {
        "default": {"model": default.model_id, "reasoning": default.reasoning},
        "max_cost_tier": MAX_COST_TIER,
        "models": [
            {
                "id": m.id,
                "label": m.label,
                "provider": m.provider,
                "blurb": m.blurb,
                "cost_tier": m.cost_tier,
                "supports_reasoning": m.supports_reasoning,
                "reasoning_options": list(m.reasoning_options),
                "default_reasoning": m.default_reasoning,
            }
            for m in available_models()
        ],
    }
