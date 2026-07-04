from typing import Protocol
from uuid import UUID

from app.domain.memory.schemas import (
    FitMemoryEntry,
    ForgetScope,
    MemoryContext,
    RecallFitContextRequest,
)


class MemoryGateway(Protocol):
    async def remember_private(self, user_id: UUID, entry: FitMemoryEntry) -> None: ...

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext: ...

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None: ...
