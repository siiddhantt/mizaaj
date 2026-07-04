from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.common import ClaimStatus


class ExtractedClaim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    subject: str
    predicate: str
    value: str
    source: str
    confidence: float = Field(ge=0, le=1)
    status: ClaimStatus = ClaimStatus.extracted
