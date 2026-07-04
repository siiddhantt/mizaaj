from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.claims import ExtractedClaim
from app.domain.common import ClothingCategory


class Measurement(BaseModel):
    name: str
    value: float
    unit: str = "cm"


class SizeMeasurementSet(BaseModel):
    size: str
    measurements: list[Measurement] = Field(default_factory=list)


class SizeLabel(BaseModel):
    label: str
    system: str | None = None
    region: str | None = None
    audience: str | None = None


class TextileComposition(BaseModel):
    material: str
    percentage: float | None = None
    component: str | None = None


class CareInstruction(BaseModel):
    instruction: str
    category: str | None = None


class ProductIdentifier(BaseModel):
    kind: str
    value: str


class ProductAttribute(BaseModel):
    name: str
    value: str


class ProductSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    brand: str | None = None
    retailer: str | None = None
    title: str
    sku: str | None = None
    url: str | None = None
    category: ClothingCategory = ClothingCategory.unknown
    color: str | None = None
    material: str | None = None
    size_options: list[str] = Field(default_factory=list)
    size_labels: list[SizeLabel] = Field(default_factory=list)
    size_chart: list[SizeMeasurementSet] = Field(default_factory=list)
    fit_descriptors: list[str] = Field(default_factory=list)
    fabric_composition: list[TextileComposition] = Field(default_factory=list)
    care_instructions: list[CareInstruction] = Field(default_factory=list)
    origin_country: str | None = None
    gender: str | None = None
    product_identifiers: list[ProductIdentifier] = Field(default_factory=list)
    attributes: list[ProductAttribute] = Field(default_factory=list)
    extracted_claims: list[ExtractedClaim] = Field(default_factory=list)
    source_capture_id: UUID | None = None


class ProductDraft(BaseModel):
    brand: str | None = None
    retailer: str | None = None
    title: str | None = None
    sku: str | None = None
    url: str | None = None
    category: ClothingCategory = ClothingCategory.unknown
    color: str | None = None
    material: str | None = None
    size_options: list[str] = Field(default_factory=list)
    size_labels: list[SizeLabel] = Field(default_factory=list)
    size_chart: list[SizeMeasurementSet] = Field(default_factory=list)
    fit_descriptors: list[str] = Field(default_factory=list)
    fabric_composition: list[TextileComposition] = Field(default_factory=list)
    care_instructions: list[CareInstruction] = Field(default_factory=list)
    origin_country: str | None = None
    gender: str | None = None
    product_identifiers: list[ProductIdentifier] = Field(default_factory=list)
    attributes: list[ProductAttribute] = Field(default_factory=list)
    extracted_claims: list[ExtractedClaim] = Field(default_factory=list)
