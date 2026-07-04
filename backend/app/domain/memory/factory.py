from app.core.config import Settings
from app.domain.memory.cognee_cloud import CogneeCloudMemoryGateway
from app.domain.memory.cognee_local import CogneeLocalMemoryGateway
from app.domain.memory.gateway import MemoryGateway


def create_memory_gateway(settings: Settings) -> MemoryGateway:
    if settings.memory_provider == "cognee_local":
        return CogneeLocalMemoryGateway(settings)
    if settings.memory_provider == "cognee_cloud":
        return CogneeCloudMemoryGateway(settings)
    raise ValueError(f"Unsupported memory provider: {settings.memory_provider}")
