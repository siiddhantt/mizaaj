from typing import Protocol

from app.domain.reasoning.schemas import GroundedReasoningRequest, GroundedReasoningResult


class ReasoningGateway(Protocol):
    async def synthesize(self, request: GroundedReasoningRequest) -> GroundedReasoningResult: ...
