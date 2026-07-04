from uuid import UUID

from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.schemas import FitMemoryEntry, ForgetScope
from app.storage.store import MizaajStore


class PrivateMemoryRebuilder:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway):
        self.store = store
        self.memory_gateway = memory_gateway

    async def rebuild_user(self, user_id: UUID) -> None:
        await self.memory_gateway.forget_private(user_id, ForgetScope.all_private)

        await self.memory_gateway.remember_private(
            user_id,
            FitMemoryEntry.from_profile(self.store.get_profile(user_id)),
        )

        for product in self._user_products(user_id):
            if product.extracted_claims:
                await self.memory_gateway.remember_private(
                    user_id,
                    FitMemoryEntry.from_product_snapshot(product),
                )

        for purchase in self.store.list_purchases(user_id):
            try:
                product = self.store.get_product(purchase.product_id)
            except Exception:
                continue
            await self.memory_gateway.remember_private(
                user_id,
                FitMemoryEntry.from_purchase(purchase, product),
            )

        for record in reversed(self.store.list_saved_memories(user_id)):
            for draft in record.remembered:
                await self.memory_gateway.remember_private(
                    user_id,
                    FitMemoryEntry(
                        subject=draft.subject,
                        text=draft.text,
                        tags=[
                            "source:ask",
                            f"kind:{draft.kind.value}",
                            *(tag for tag in draft.tags if tag),
                        ],
                        source_id=str(draft.id),
                    ),
                )

    def _user_products(self, user_id: UUID):
        for product in self.store.list_products():
            if product.source_capture_id is None:
                continue
            try:
                capture = self.store.get_capture(product.source_capture_id)
            except Exception:
                continue
            if capture.user_id == user_id:
                yield product
