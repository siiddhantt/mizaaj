from uuid import UUID

from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.rebuilder import PrivateMemoryRebuilder
from app.domain.profiles.schemas import FitProfile, FitProfileUpdate
from app.storage.store import MizaajStore


class ProfileService:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway | None = None):
        self.store = store
        self.memory_gateway = memory_gateway

    def get_profile(self, user_id: UUID) -> FitProfile:
        return self.store.get_profile(user_id)

    async def update_profile(self, user_id: UUID, payload: FitProfileUpdate) -> FitProfile:
        profile = self.store.update_profile(user_id, payload)
        if self.memory_gateway is not None:
            await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return profile
