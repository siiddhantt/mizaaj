from datetime import date
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.common import FitOutcome


class PurchaseCreate(BaseModel):
    user_id: UUID
    product_id: UUID
    purchased_size: str
    outcome: FitOutcome = FitOutcome.unknown
    purchased_at: date | None = None
    fit_rating: int = Field(default=3, ge=1, le=5)
    comfort_rating: int = Field(default=3, ge=1, le=5)
    silhouette_rating: int = Field(default=3, ge=1, le=5)
    fit_notes: str | None = None


class PurchaseRecord(PurchaseCreate):
    id: UUID = Field(default_factory=uuid4)


class PurchaseUpdate(BaseModel):
    purchased_size: str | None = None
    outcome: FitOutcome | None = None
    purchased_at: date | None = None
    fit_rating: int | None = Field(default=None, ge=1, le=5)
    comfort_rating: int | None = Field(default=None, ge=1, le=5)
    silhouette_rating: int | None = Field(default=None, ge=1, le=5)
    fit_notes: str | None = None
