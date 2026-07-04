from typing import Protocol

from app.domain.uploads.schemas import UploadIntentRequest, UploadIntentResponse


class UploadGateway(Protocol):
    async def create_intent(self, request: UploadIntentRequest) -> UploadIntentResponse: ...
