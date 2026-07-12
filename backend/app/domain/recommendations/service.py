from app.domain.common import FitOutcome
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.schemas import MemoryContext, RecallFitContextRequest
from app.domain.products.schemas import ProductSnapshot, SizeMeasurementSet
from app.domain.profiles.schemas import FitProfile
from app.domain.purchases.schemas import PurchaseRecord
from app.domain.recommendations.schemas import (
    RecommendationEvidence,
    RecommendationRequest,
    RecommendationResponse,
)
from app.storage.store import MizaajStore


class RecommendationService:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway):
        self.store = store
        self.memory_gateway = memory_gateway

    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        product = self.store.get_product(request.product_id)
        profile = self.store.get_profile(request.user_id)
        purchases = self.store.list_purchases(request.user_id)
        capture_note = self._source_capture_note(product)
        same_brand = [item for item in purchases if self._same_brand_category(item, product)]
        private_notes = self._private_notes(profile, capture_note)
        remembered = await self._recall_memory(
            RecallFitContextRequest(
                user_id=request.user_id,
                query=(
                    f"{product.brand or ''} {product.title} {product.category.value} "
                    f"{request.target_fit or ''} size fit return tight loose shoulder"
                ),
                top_k=4,
            )
        )

        recommended_size = self._pick_size(
            product,
            same_brand,
            profile,
            private_notes,
        )
        confidence = self._confidence(
            same_brand,
            remembered.facts,
            product.size_chart,
            private_notes,
        )
        risks = self._risks(product, remembered.facts, same_brand, private_notes)
        evidence = self._evidence(
            product,
            recommended_size,
            same_brand,
            remembered.facts,
            private_notes,
        )
        summary = self._summary(product, recommended_size, confidence, same_brand, private_notes)

        return RecommendationResponse(
            user_id=request.user_id,
            product_id=request.product_id,
            recommended_size=recommended_size,
            confidence=confidence,
            summary=summary,
            risks=risks,
            evidence=evidence,
        )

    async def _recall_memory(self, query: RecallFitContextRequest) -> MemoryContext:
        try:
            return await self.memory_gateway.recall_private(query)
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            return MemoryContext.degraded(query.user_id, query.query, error)

    def _pick_size(
        self,
        product: ProductSnapshot,
        same_brand: list[PurchaseRecord],
        profile: FitProfile,
        private_notes: list[str],
    ) -> str | None:
        options = product.size_options
        kept = [item for item in same_brand if item.outcome == FitOutcome.kept]
        if kept:
            return kept[-1].purchased_size

        preferred = next(
            (item for item in profile.category_preferences if item.category == product.category),
            None,
        )
        if preferred and preferred.usual_size in options:
            return preferred.usual_size

        noted_size = self._size_from_notes(options, private_notes)
        if noted_size:
            return noted_size

        return options[(len(options) - 1) // 2] if options else None

    def _confidence(
        self,
        same_brand: list[PurchaseRecord],
        facts: list,
        size_chart: list[SizeMeasurementSet],
        private_notes: list[str],
    ) -> float:
        value = 0.36
        if size_chart:
            value += 0.18
        if private_notes:
            value += 0.08
        if facts:
            value += min(0.2, len(facts) * 0.04)
        if same_brand:
            value += min(0.24, len(same_brand) * 0.08)
        return min(value, 0.88)

    def _risks(
        self,
        product: ProductSnapshot,
        facts: list,
        same_brand: list[PurchaseRecord],
        private_notes: list[str],
    ) -> list[str]:
        risks = []
        memory_text = " ".join([*(fact.text.lower() for fact in facts), *private_notes])
        if "tight" in memory_text:
            risks.append("Past memory mentions tight fit; check chest and shoulder measurements.")
        if "returned" in memory_text:
            risks.append("You have returned a similar item before; confidence stays conservative.")
        if product.material and "linen" in product.material.lower():
            risks.append("Linen can relax through the day; avoid sizing up only for stiffness.")
        if not same_brand:
            risks.append("No confirmed purchase history for this brand and category yet.")
        return risks

    def _evidence(
        self,
        product: ProductSnapshot,
        recommended_size: str | None,
        same_brand: list[PurchaseRecord],
        facts: list,
        private_notes: list[str],
    ) -> list[RecommendationEvidence]:
        evidence = [
            RecommendationEvidence(
                label="Past purchase",
                detail=(
                    f"Size {item.purchased_size}: {item.outcome.value}."
                    + (
                        " "
                        + ", ".join(
                            f"{label} {value}/5"
                            for label, value in [
                                ("fit", item.fit_rating),
                                ("comfort", item.comfort_rating),
                            ]
                            if value is not None
                        )
                        if item.fit_rating is not None or item.comfort_rating is not None
                        else ""
                    )
                ),
                source=str(item.id),
            )
            for item in same_brand[-3:]
        ]
        if recommended_size:
            measurements = self._measurements_for(product.size_chart, recommended_size)
            if measurements:
                evidence.append(
                    RecommendationEvidence(
                        label="Size chart",
                        detail=f"Size {recommended_size}: {measurements}.",
                        source=str(product.id),
                    )
                )
        if private_notes:
            evidence.append(
                RecommendationEvidence(
                    label="Private note",
                    detail=private_notes[0],
                    source=str(product.source_capture_id or product.id),
                )
            )
        evidence.extend(
            RecommendationEvidence(label="Cognee memory", detail=fact.text, source=fact.source)
            for fact in facts[:4]
        )
        return evidence

    def _summary(
        self,
        product: ProductSnapshot,
        size: str | None,
        confidence: float,
        same_brand: list[PurchaseRecord],
        private_notes: list[str],
    ) -> str:
        if same_brand:
            return (
                f"Recommended {size} because your confirmed {product.brand or 'brand'} history "
                "has similar category evidence."
            )
        if private_notes and product.size_chart:
            return f"Recommended {size} using the product size chart and your private fit notes."
        if confidence < 0.55:
            return (
                f"Recommended {size} with low confidence because this brand is new to your memory."
            )
        return f"Recommended {size} based on profile, size chart, and remembered fit signals."

    def _same_brand_category(self, purchase: PurchaseRecord, product: ProductSnapshot) -> bool:
        purchased_product = self.store.get_product(purchase.product_id)
        return (
            purchased_product.brand == product.brand
            and purchased_product.category == product.category
        )

    def _source_capture_note(self, product: ProductSnapshot) -> str | None:
        if not product.source_capture_id:
            return None
        try:
            return self.store.get_capture(product.source_capture_id).user_notes
        except Exception:
            return None

    def _private_notes(self, profile: FitProfile, capture_note: str | None) -> list[str]:
        values = [
            *(profile.sensitivities or []),
            profile.body_notes,
            *(preference.notes for preference in profile.category_preferences),
            capture_note,
        ]
        return [value.strip().lower() for value in values if value and value.strip()]

    def _size_from_notes(self, options: list[str], notes: list[str]) -> str | None:
        normalized = " ".join(notes).lower()
        for option in sorted(options, key=len, reverse=True):
            token = option.lower()
            patterns = (
                f"size {token}",
                f"buy {token}",
                f"wear {token}",
                f"{token} in",
                f"usually {token}",
            )
            if any(pattern in normalized for pattern in patterns):
                return option
        return None

    def _measurements_for(self, size_chart: list[SizeMeasurementSet], size: str) -> str | None:
        row = next((item for item in size_chart if item.size.lower() == size.lower()), None)
        if not row:
            return None
        return ", ".join(
            f"{measurement.name.replace('_', ' ')} {measurement.value:g}{measurement.unit}"
            for measurement in row.measurements[:4]
        )
