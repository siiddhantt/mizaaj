from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.common import ClothingCategory, FitPreference


class CategorySizePreference(BaseModel):
    category: ClothingCategory
    usual_size: str
    preferred_fit: FitPreference = FitPreference.regular
    notes: str | None = None


class FitProfile(BaseModel):
    user_id: UUID
    display_name: str
    height_cm: int | None = Field(default=None, ge=80, le=260)
    weight_kg: int | None = Field(default=None, ge=25, le=250)
    body_notes: str | None = None
    sensitivities: list[str] = Field(default_factory=list)
    category_preferences: list[CategorySizePreference] = Field(default_factory=list)


class FitProfileUpdate(BaseModel):
    display_name: str | None = None
    height_cm: int | None = Field(default=None, ge=80, le=260)
    weight_kg: int | None = Field(default=None, ge=25, le=250)
    body_notes: str | None = None
    sensitivities: list[str] | None = None
    category_preferences: list[CategorySizePreference] | None = None
