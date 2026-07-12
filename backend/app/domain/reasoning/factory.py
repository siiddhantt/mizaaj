from app.core.config import Settings
from app.domain.reasoning.gateway import ReasoningGateway
from app.domain.reasoning.openrouter import OpenRouterReasoningGateway


def create_reasoning_gateway(settings: Settings) -> ReasoningGateway | None:
    if not settings.openrouter_api_key:
        return None
    return OpenRouterReasoningGateway(settings)
