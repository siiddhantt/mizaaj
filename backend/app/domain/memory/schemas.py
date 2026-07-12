from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.products.schemas import ProductSnapshot
from app.domain.profiles.schemas import FitProfile
from app.domain.purchases.schemas import PurchaseRecord


class ForgetScope(StrEnum):
    all_private = "all_private"
    profile = "profile"
    purchases = "purchases"
    captures = "captures"


class FitMemoryEntry(BaseModel):
    subject: str
    text: str
    tags: list[str] = Field(default_factory=list)
    source_id: str | None = None

    @classmethod
    def from_profile(cls, profile: FitProfile) -> "FitMemoryEntry":
        preferences = [
            f"{item.category.value}: usually {item.usual_size}, prefers {item.preferred_fit.value}"
            for item in profile.category_preferences
        ]
        body = [
            f"Fit profile for {profile.display_name}.",
            f"Sensitivities: {', '.join(profile.sensitivities) or 'none recorded'}.",
            f"Category preferences: {'; '.join(preferences) or 'none recorded'}.",
        ]
        if profile.body_notes:
            body.append(f"Body notes: {profile.body_notes}.")
        return cls(
            subject=f"user:{profile.user_id}:fit_profile",
            text=" ".join(body),
            tags=["source:profile", f"user:{profile.user_id}"],
            source_id=str(profile.user_id),
        )

    @classmethod
    def from_product_snapshot(cls, product: ProductSnapshot) -> "FitMemoryEntry":
        claims = [
            f"{claim.predicate} is {claim.value} from {claim.source}"
            for claim in product.extracted_claims
        ]
        size_labels = [
            " ".join(part for part in [item.system, item.label] if part).strip()
            for item in product.size_labels
        ]
        composition = [
            " ".join(
                part
                for part in [
                    f"{item.percentage:g}%" if item.percentage is not None else None,
                    item.material,
                    f"({item.component})" if item.component else None,
                ]
                if part
            )
            for item in product.fabric_composition
        ]
        care = [item.instruction for item in product.care_instructions]
        identifiers = ", ".join(f"{item.kind} {item.value}" for item in product.product_identifiers)
        details = [
            f"Observed size labels: {', '.join(size_labels)}." if size_labels else None,
            f"Fit descriptors: {', '.join(product.fit_descriptors)}."
            if product.fit_descriptors
            else None,
            f"Fabric composition: {', '.join(composition)}." if composition else None,
            f"Care instructions: {', '.join(care)}." if care else None,
            f"Origin country: {product.origin_country}." if product.origin_country else None,
            f"Product identifiers: {identifiers}." if identifiers else None,
        ]
        return cls(
            subject=f"product:{product.id}",
            text=(
                f"Captured product {product.title} by {product.brand or 'unknown brand'} "
                f"in category {product.category.value}. "
                f"{' '.join(item for item in details if item)} "
                f"Confirmed facts: {'; '.join(claims)}."
            ),
            tags=[
                "source:capture",
                f"product:{product.id}",
                f"brand:{(product.brand or 'unknown').lower()}",
                f"category:{product.category.value}",
            ],
            source_id=str(product.id),
        )

    @classmethod
    def from_purchase(cls, purchase: PurchaseRecord, product: ProductSnapshot) -> "FitMemoryEntry":
        ratings = ", ".join(
            f"{label} {value}/5"
            for label, value in [
                ("fit", purchase.fit_rating),
                ("comfort", purchase.comfort_rating),
                ("silhouette", purchase.silhouette_rating),
            ]
            if value is not None
        )
        return cls(
            subject=f"purchase:{purchase.id}",
            text=(
                f"User bought {product.title} by {product.brand or 'unknown brand'} "
                f"in size {purchase.purchased_size}. Outcome: {purchase.outcome.value}. "
                f"{f'Ratings: {ratings}. ' if ratings else ''}"
                f"Notes: {purchase.fit_notes or 'none'}."
            ),
            tags=[
                "source:purchase",
                f"product:{product.id}",
                f"brand:{(product.brand or 'unknown').lower()}",
                f"category:{product.category.value}",
                f"outcome:{purchase.outcome.value}",
            ],
            source_id=str(purchase.id),
        )


class RecallFitContextRequest(BaseModel):
    user_id: UUID
    query: str
    top_k: int = Field(default=8, ge=1, le=20)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)


class MemoryContextFact(BaseModel):
    text: str
    source: str
    score: float | None = None


class MemoryContext(BaseModel):
    user_id: UUID
    query: str
    facts: list[MemoryContextFact] = Field(default_factory=list)
    status: Literal["ready", "degraded"] = "ready"
    error: str | None = None

    @classmethod
    def degraded(cls, user_id: UUID, query: str, error: str) -> "MemoryContext":
        return cls(user_id=user_id, query=query, status="degraded", error=error)
