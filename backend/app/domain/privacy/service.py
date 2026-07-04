from uuid import UUID

from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.schemas import ForgetScope
from app.domain.privacy.schemas import UserDataDeletionResult
from app.storage.store import MizaajStore


class PrivacyService:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway):
        self.store = store
        self.memory_gateway = memory_gateway

    async def delete_user_data(self, user_id: UUID) -> UserDataDeletionResult:
        result = self.store.delete_user_data(user_id)
        await self.memory_gateway.forget_private(user_id, ForgetScope.all_private)
        return result.model_copy(update={"cognee_memory_deleted": True})
