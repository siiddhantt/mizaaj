from app.core.config import Settings
from app.domain.extraction.gateway import ExtractionGateway
from app.domain.extraction.openrouter import OpenRouterExtractionGateway


def create_extraction_gateway(settings: Settings) -> ExtractionGateway:
    if settings.extraction_provider == "openrouter":
        return OpenRouterExtractionGateway(settings)
    raise ValueError(f"Unsupported extraction provider: {settings.extraction_provider}")
