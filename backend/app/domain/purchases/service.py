from uuid import UUID

from app.core.errors import ForbiddenError
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.rebuilder import PrivateMemoryRebuilder
from app.domain.memory.schemas import FitMemoryEntry
from app.domain.purchases.schemas import PurchaseCreate, PurchaseRecord, PurchaseUpdate
from app.storage.store import MizaajStore


class PurchaseService:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway | None = None):
        self.store = store
        self.memory_gateway = memory_gateway

    def list_purchases(self, user_id: UUID) -> list[PurchaseRecord]:
        return self.store.list_purchases(user_id)

    def get_purchase(self, user_id: UUID, purchase_id: UUID) -> PurchaseRecord:
        purchase = self.store.get_purchase(purchase_id)
        self._assert_owner(user_id, purchase)
        return purchase

    async def create_purchase(self, payload: PurchaseCreate) -> PurchaseRecord:
        product = self.store.get_product(payload.product_id)
        purchase = self.store.save_purchase(PurchaseRecord(**payload.model_dump()))
        if self.memory_gateway is not None:
            await self.memory_gateway.remember_private(
                payload.user_id,
                FitMemoryEntry.from_purchase(purchase, product),
            )
        return purchase

    async def update_purchase(
        self,
        user_id: UUID,
        purchase_id: UUID,
        payload: PurchaseUpdate,
    ) -> PurchaseRecord:
        purchase = self.get_purchase(user_id, purchase_id)
        updated = purchase.model_copy(update=payload.model_dump(exclude_none=True))
        saved = self.store.save_purchase(updated)
        if self.memory_gateway is not None:
            await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return saved

    async def delete_purchase(self, user_id: UUID, purchase_id: UUID) -> PurchaseRecord:
        self.get_purchase(user_id, purchase_id)
        deleted = self.store.delete_purchase(purchase_id)
        if self.memory_gateway is not None:
            await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return deleted

    def _assert_owner(self, user_id: UUID, purchase: PurchaseRecord) -> None:
        if purchase.user_id != user_id:
            raise ForbiddenError("Purchase record does not belong to the current user")
