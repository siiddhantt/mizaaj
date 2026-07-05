from app.core.config import Settings
from app.domain.atlas.cognee_cloud import CogneeCloudAtlasGateway
from app.domain.atlas.disabled import DisabledAtlasGateway
from app.domain.atlas.gateway import AtlasGateway
from app.domain.atlas.seed import SeedAtlasGateway


def create_atlas_gateway(settings: Settings) -> AtlasGateway:
    if settings.atlas_provider == "disabled":
        return DisabledAtlasGateway()
    if settings.atlas_provider == "seed":
        return SeedAtlasGateway()
    if settings.atlas_provider == "cognee_cloud":
        return CogneeCloudAtlasGateway(settings)
    raise ValueError(f"Unsupported atlas provider: {settings.atlas_provider}")
