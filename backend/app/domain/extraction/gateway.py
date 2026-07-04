from typing import Protocol

from app.domain.captures.schemas import CaptureCreate
from app.domain.products.schemas import ProductDraft


class ExtractionGateway(Protocol):
    async def extract_product(self, capture: CaptureCreate) -> ProductDraft: ...
