from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.common import CaptureSourceType, ClaimStatus, ClothingCategory
from app.domain.products.schemas import ProductDraft, ProductSnapshot


class UploadedAsset(BaseModel):
    path: str
    mime_type: str | None = None
    original_name: str | None = None
    public_url: str | None = None


class CaptureCreate(BaseModel):
    user_id: UUID
    source_type: CaptureSourceType
    page_url: str | None = None
    text_blocks: list[str] = Field(default_factory=list)
    assets: list[UploadedAsset] = Field(default_factory=list)
    user_notes: str | None = None


class CaptureResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    source_type: CaptureSourceType
    page_url: str | None = None
    text_blocks: list[str] = Field(default_factory=list)
    assets: list[UploadedAsset] = Field(default_factory=list)
    user_notes: str | None = None
    product_draft: ProductDraft
    product_snapshot: ProductSnapshot | None = None
    linked_product_id: UUID | None = None
    confirmed: bool = False
    memory_status: str = "not_indexed"
    memory_error: str | None = None


class ConfirmCaptureRequest(BaseModel):
    product_draft: ProductDraft
    accepted_claim_ids: list[UUID] = Field(default_factory=list)

    def accepted_draft(self) -> ProductDraft:
        accepted = {
            claim.id: claim.model_copy(update={"status": ClaimStatus.user_confirmed})
            for claim in self.product_draft.extracted_claims
            if claim.id in self.accepted_claim_ids
        }
        rejected_predicates = {
            claim.predicate.strip().lower()
            for claim in self.product_draft.extracted_claims
            if claim.id not in self.accepted_claim_ids
        }
        field_updates = {
            field: value
            for predicate, (field, value) in _REJECTED_CLAIM_FIELDS.items()
            if predicate in rejected_predicates
        }
        return self.product_draft.model_copy(
            update={**field_updates, "extracted_claims": list(accepted.values())}
        )


_REJECTED_CLAIM_FIELDS = {
    "category": ("category", ClothingCategory.unknown),
    "material": ("material", None),
    "available_sizes": ("size_options", []),
    "regional_size_labels": ("size_labels", []),
    "size_chart": ("size_chart", []),
    "fit": ("fit_descriptors", []),
    "fabric_composition": ("fabric_composition", []),
    "care": ("care_instructions", []),
    "origin_country": ("origin_country", None),
    "gender": ("gender", None),
    "product_identifiers": ("product_identifiers", []),
    "color": ("color", None),
}
