from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.memory.schemas import MemoryContextFact


class MemoryDraftKind(StrEnum):
    product_fact = "product_fact"
    fit_preference = "fit_preference"
    fit_outcome = "fit_outcome"
    brand_pattern = "brand_pattern"
    size_mapping = "size_mapping"
    uncertainty = "uncertainty"


class AskFitRequest(BaseModel):
    user_id: UUID
    question: str = Field(min_length=1, max_length=1200)
    product_id: UUID | None = None
    capture_id: UUID | None = None
    context_notes: str | None = Field(default=None, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)


class AskEvidence(BaseModel):
    label: str
    detail: str
    source: str


class MemoryDraft(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: MemoryDraftKind
    subject: str
    text: str
    source: str = "ask"
    confidence: float = Field(default=0.65, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)


class AskFitResponse(BaseModel):
    user_id: UUID
    question: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[AskEvidence] = Field(default_factory=list)
    recalled_facts: list[MemoryContextFact] = Field(default_factory=list)
    memory_drafts: list[MemoryDraft] = Field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SavedMemoryRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    question: str
    answer: str
    product_id: UUID | None = None
    capture_id: UUID | None = None
    evidence: list[AskEvidence] = Field(default_factory=list)
    recalled_facts: list[MemoryContextFact] = Field(default_factory=list)
    remembered: list[MemoryDraft] = Field(default_factory=list)
    memory_status: str
    memory_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class RememberMemoryDraftsRequest(BaseModel):
    user_id: UUID
    drafts: list[MemoryDraft] = Field(default_factory=list)
    question: str | None = None
    answer: str | None = None
    product_id: UUID | None = None
    capture_id: UUID | None = None
    evidence: list[AskEvidence] = Field(default_factory=list)
    recalled_facts: list[MemoryContextFact] = Field(default_factory=list)


class RememberMemoryDraftsResponse(BaseModel):
    user_id: UUID
    remembered: list[MemoryDraft] = Field(default_factory=list)
    memory_status: str
    memory_error: str | None = None
    memory_record: SavedMemoryRecord | None = None
