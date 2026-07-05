from typing import Protocol

from app.domain.atlas.schemas import AtlasContext, AtlasRecallRequest


class AtlasGateway(Protocol):
    async def recall_public(self, request: AtlasRecallRequest) -> AtlasContext: ...
