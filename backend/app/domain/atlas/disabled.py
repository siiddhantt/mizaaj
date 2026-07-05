from app.domain.atlas.gateway import AtlasGateway
from app.domain.atlas.schemas import AtlasContext, AtlasRecallRequest


class DisabledAtlasGateway(AtlasGateway):
    async def recall_public(self, request: AtlasRecallRequest) -> AtlasContext:
        return AtlasContext.disabled(request.query)
