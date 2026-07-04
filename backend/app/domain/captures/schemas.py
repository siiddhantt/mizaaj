from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.common import CaptureSourceType, ClaimStatus
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
        return self.product_draft.model_copy(update={"extracted_claims": list(accepted.values())})
