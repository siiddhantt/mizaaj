from uuid import UUID

from app.core.errors import ForbiddenError
from app.domain.products.identity import fallback_title, is_generic_title, product_from_draft
from app.domain.products.schemas import ProductSnapshot
from app.storage.store import MizaajStore


class ProductService:
    def __init__(self, store: MizaajStore):
        self.store = store

    def list_products(self) -> list[ProductSnapshot]:
        return self.store.list_products()

    def backfill_saved_memory_products(self, user_id: UUID) -> None:
        for record in self.store.list_saved_memories(user_id):
            if record.product_id is not None:
                if record.capture_id is not None:
                    capture = self.store.get_capture(record.capture_id)
                    if capture.user_id != user_id:
                        raise ForbiddenError("Saved memory capture belongs to a different user")
                    if capture.linked_product_id != record.product_id:
                        self.store.save_capture(
                            capture.model_copy(update={"linked_product_id": record.product_id})
                        )
                continue
            if record.capture_id is None:
                continue

            try:
                capture = self.store.get_capture(record.capture_id)
            except Exception:
                continue

            if capture.user_id != user_id:
                raise ForbiddenError("Saved memory capture belongs to a different user")

            product = self._memory_product(capture)
            self.store.save_product(product)
            self.store.save_capture(
                capture.model_copy(
                    update={
                        "product_snapshot": product,
                        "confirmed": True,
                        "memory_status": capture.memory_status,
                    }
                )
            )
            self.store.save_memory_record(record.model_copy(update={"product_id": product.id}))

    def get_product(self, product_id: UUID) -> ProductSnapshot:
        return self.store.get_product(product_id)

    def _memory_product(self, capture) -> ProductSnapshot:
        if capture.product_snapshot is None:
            return product_from_draft(
                capture.product_draft,
                source_capture_id=capture.id,
                url=capture.page_url,
            )
        product = capture.product_snapshot
        if is_generic_title(product.title, product.category.value):
            return product.model_copy(update={"title": fallback_title(capture.product_draft)})
        return product
