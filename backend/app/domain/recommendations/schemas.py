from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    user_id: UUID
    product_id: UUID
    target_fit: str | None = None


class RecommendationEvidence(BaseModel):
    label: str
    detail: str
    source: str


class RecommendationResponse(BaseModel):
    user_id: UUID
    product_id: UUID
    recommended_size: str | None
    confidence: float = Field(ge=0, le=1)
    summary: str
    risks: list[str] = Field(default_factory=list)
    evidence: list[RecommendationEvidence] = Field(default_factory=list)
