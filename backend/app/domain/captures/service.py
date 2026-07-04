from uuid import UUID

from app.core.errors import ForbiddenError
from app.domain.captures.schemas import CaptureCreate, CaptureResponse, ConfirmCaptureRequest
from app.domain.extraction.gateway import ExtractionGateway
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.rebuilder import PrivateMemoryRebuilder
from app.domain.memory.schemas import FitMemoryEntry
from app.domain.products.identity import product_from_draft
from app.storage.store import MizaajStore


class CaptureService:
    def __init__(
        self,
        store: MizaajStore,
        extractor: ExtractionGateway | None = None,
        memory_gateway: MemoryGateway | None = None,
    ):
        self.store = store
        self.extractor = extractor
        self.memory_gateway = memory_gateway

    async def create_capture(self, payload: CaptureCreate) -> CaptureResponse:
        if self.extractor is None:
            raise RuntimeError("CaptureService requires an extraction gateway")
        draft = await self.extractor.extract_product(payload)
        capture = CaptureResponse(**payload.model_dump(), product_draft=draft)
        self.store.save_capture(capture)
        return capture

    def list_captures(self, user_id: UUID) -> list[CaptureResponse]:
        return self.store.list_captures(user_id)

    def get_capture(self, user_id: UUID, capture_id: UUID) -> CaptureResponse:
        capture = self.store.get_capture(capture_id)
        self._assert_owner(user_id, capture)
        return capture

    async def confirm_capture(
        self,
        capture_id: UUID,
        payload: ConfirmCaptureRequest,
    ) -> CaptureResponse:
        capture = self.store.get_capture(capture_id)
        if capture.confirmed:
            return capture

        draft = payload.accepted_draft()
        product = product_from_draft(draft, source_capture_id=capture_id, url=capture.page_url)

        if self.memory_gateway is None:
            raise RuntimeError("CaptureService requires a memory gateway")

        confirmed = capture.model_copy(
            update={
                "product_draft": draft,
                "product_snapshot": product,
                "confirmed": True,
                "memory_status": "indexing" if product.extracted_claims else "not_indexed",
                "memory_error": None,
            }
        )
        self.store.save_product(product)
        self.store.save_capture(confirmed)

        memory_status = "not_indexed"
        memory_error = None
        if product.extracted_claims:
            try:
                await self.memory_gateway.remember_private(
                    capture.user_id,
                    FitMemoryEntry.from_product_snapshot(product),
                )
                memory_status = "indexed"
            except Exception as exc:
                memory_status = "failed"
                memory_error = str(exc) or exc.__class__.__name__

        confirmed = confirmed.model_copy(
            update={
                "memory_status": memory_status,
                "memory_error": memory_error,
            }
        )
        self.store.save_capture(confirmed)
        return confirmed

    async def delete_capture(self, user_id: UUID, capture_id: UUID) -> CaptureResponse:
        capture = self.get_capture(user_id, capture_id)

        if capture.confirmed and capture.product_snapshot is not None:
            purchases = [
                purchase
                for purchase in self.store.list_purchases(user_id)
                if purchase.product_id == capture.product_snapshot.id
            ]
            if purchases:
                raise ForbiddenError("Cannot delete a confirmed capture with saved outcomes")
            self.store.delete_product(capture.product_snapshot.id)

        deleted = self.store.delete_capture(capture_id)
        if capture.confirmed and self.memory_gateway is not None:
            await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return deleted

    def _assert_owner(self, user_id: UUID, capture: CaptureResponse) -> None:
        if capture.user_id != user_id:
            raise ForbiddenError("Capture does not belong to the current user")
