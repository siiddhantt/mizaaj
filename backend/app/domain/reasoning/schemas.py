from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ask.schemas import (
    AskEvidence,
    ConversationTurn,
    MemoryDraft,
    MemoryDraftKind,
    OutcomeDraft,
)
from app.domain.common import FitOutcome
from app.domain.products.schemas import ProductSnapshot
from app.domain.profiles.schemas import FitProfile
from app.domain.purchases.schemas import PurchaseRecord


class GroundedReasoningRequest(BaseModel):
    user_id: UUID
    question: str
    context_notes: str | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)
    profile: FitProfile
    product: ProductSnapshot | None = None
    purchases: list[PurchaseRecord] = Field(default_factory=list)
    evidence: list[AskEvidence] = Field(default_factory=list)


class ProposedMemory(BaseModel):
    kind: MemoryDraftKind
    scope: Literal["user", "product"]
    text: str = Field(min_length=1, max_length=700)
    confidence: float = Field(ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=8)

    model_config = ConfigDict(extra="forbid")


class ProposedOutcome(BaseModel):
    purchased_size: str | None
    outcome: FitOutcome
    fit_rating: int | None = Field(ge=1, le=5)
    comfort_rating: int | None = Field(ge=1, le=5)
    silhouette_rating: int | None = Field(ge=1, le=5)
    fit_notes: str
    confidence: float = Field(ge=0, le=1)

    model_config = ConfigDict(extra="forbid")


class ReasoningPayload(BaseModel):
    answer_markdown: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)
    used_evidence_sources: list[str] = Field(default_factory=list)
    memory_drafts: list[ProposedMemory] = Field(default_factory=list, max_length=6)
    outcome_draft: ProposedOutcome | None

    model_config = ConfigDict(extra="forbid")


class GroundedReasoningResult(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    used_evidence_sources: list[str] = Field(default_factory=list)
    memory_drafts: list[MemoryDraft] = Field(default_factory=list)
    outcome_draft: OutcomeDraft | None = None
