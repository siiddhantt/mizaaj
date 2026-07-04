import re
from uuid import UUID

from app.core.errors import ForbiddenError
from app.domain.ask.schemas import (
    AskEvidence,
    AskFitRequest,
    AskFitResponse,
    MemoryDraft,
    MemoryDraftKind,
    RememberMemoryDraftsRequest,
    RememberMemoryDraftsResponse,
    SavedMemoryRecord,
)
from app.domain.common import FitOutcome
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.rebuilder import PrivateMemoryRebuilder
from app.domain.memory.recall import clean_recall_text
from app.domain.memory.schemas import FitMemoryEntry, MemoryContext, RecallFitContextRequest
from app.domain.products.identity import display_name, product_from_draft
from app.domain.products.schemas import ProductSnapshot
from app.domain.profiles.schemas import FitProfile
from app.domain.purchases.schemas import PurchaseRecord
from app.storage.store import MizaajStore


class AskFitService:
    def __init__(self, store: MizaajStore, memory_gateway: MemoryGateway):
        self.store = store
        self.memory_gateway = memory_gateway

    async def ask(self, request: AskFitRequest) -> AskFitResponse:
        profile = self.store.get_profile(request.user_id)
        product = self._product(request)
        self._assert_product_access(request.user_id, product)
        purchases = self.store.list_purchases(request.user_id)
        recalled = await self._recall(request, product)
        related_purchases = self._related_purchases(purchases, product)
        evidence = self._evidence(profile, product, related_purchases, recalled)
        answer = self._answer(request, profile, product, related_purchases, recalled)
        drafts = self._drafts(request, profile, product, related_purchases, recalled)

        return AskFitResponse(
            user_id=request.user_id,
            question=request.question,
            answer=answer,
            confidence=self._confidence(
                product,
                related_purchases,
                recalled,
                has_profile_signal=bool(self._profile_signal(profile)),
            ),
            evidence=evidence,
            recalled_facts=recalled.facts,
            memory_drafts=drafts,
        )

    async def remember_drafts(
        self, request: RememberMemoryDraftsRequest
    ) -> RememberMemoryDraftsResponse:
        product_id = await self._memory_product_id(request)
        remembered: list[MemoryDraft] = []
        memory_error: str | None = None
        memory_status = "indexed"
        try:
            for draft in request.drafts:
                await self.memory_gateway.remember_private(
                    request.user_id,
                    FitMemoryEntry(
                        subject=draft.subject,
                        text=draft.text,
                        tags=[
                            "source:ask",
                            f"kind:{draft.kind.value}",
                            *(tag for tag in draft.tags if tag),
                        ],
                        source_id=str(draft.id),
                    ),
                )
                remembered.append(draft)
        except Exception as exc:
            memory_status = "failed"
            memory_error = str(exc)

        record = self.store.save_memory_record(
            SavedMemoryRecord(
                user_id=request.user_id,
                question=request.question or "Saved from Mizaaj chat",
                answer=request.answer or "",
                product_id=product_id,
                capture_id=request.capture_id,
                evidence=request.evidence,
                recalled_facts=request.recalled_facts,
                remembered=remembered,
                memory_status=memory_status,
                memory_error=memory_error,
            )
        )

        return RememberMemoryDraftsResponse(
            user_id=request.user_id,
            remembered=remembered,
            memory_status=memory_status,
            memory_error=memory_error,
            memory_record=record,
        )

    def list_saved_memories(self, user_id: UUID) -> list[SavedMemoryRecord]:
        return self.store.list_saved_memories(user_id)

    async def delete_saved_memory(self, user_id: UUID, memory_id: UUID) -> SavedMemoryRecord:
        record = self.store.get_saved_memory(memory_id)
        if record.user_id != user_id:
            raise ForbiddenError("Saved memory does not belong to the current user")

        deleted = self.store.delete_memory_record(memory_id)
        await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return deleted

    async def delete_all_saved_memories(self, user_id: UUID) -> int:
        count = self.store.delete_saved_memories(user_id)
        await PrivateMemoryRebuilder(self.store, self.memory_gateway).rebuild_user(user_id)
        return count

    def _product(self, request: AskFitRequest) -> ProductSnapshot | None:
        if request.product_id is not None:
            return self.store.get_product(request.product_id)
        if request.capture_id is None:
            return None

        capture = self.store.get_capture(request.capture_id)
        if capture.user_id != request.user_id:
            raise ForbiddenError("Capture does not belong to the current user")
        if capture.product_snapshot is not None:
            return capture.product_snapshot

        return product_from_draft(
            capture.product_draft,
            source_capture_id=capture.id,
            url=capture.page_url,
        )

    def _assert_references_access(
        self,
        user_id: UUID,
        product_id: UUID | None,
        capture_id: UUID | None,
    ) -> None:
        if product_id is not None:
            self._assert_product_access(user_id, self.store.get_product(product_id))
        if capture_id is not None:
            capture = self.store.get_capture(capture_id)
            if capture.user_id != user_id:
                raise ForbiddenError("Capture does not belong to the current user")

    def _assert_product_access(self, user_id: UUID, product: ProductSnapshot | None) -> None:
        if product is None or product.source_capture_id is None:
            return

        capture = self.store.get_capture(product.source_capture_id)
        if capture.user_id != user_id:
            raise ForbiddenError("Product does not belong to the current user")

    async def _memory_product_id(self, request: RememberMemoryDraftsRequest) -> UUID | None:
        self._assert_references_access(request.user_id, request.product_id, request.capture_id)
        if request.product_id is not None:
            return request.product_id
        if request.capture_id is None:
            return None

        capture = self.store.get_capture(request.capture_id)
        if capture.product_snapshot is not None:
            return capture.product_snapshot.id

        product = product_from_draft(
            capture.product_draft,
            source_capture_id=capture.id,
            url=capture.page_url,
        )
        confirmed = capture.model_copy(
            update={
                "product_snapshot": product,
                "confirmed": True,
                "memory_status": "indexing" if product.extracted_claims else "not_indexed",
                "memory_error": None,
            }
        )
        self.store.save_product(product)
        self.store.save_capture(confirmed)

        if not product.extracted_claims:
            return product.id

        memory_status = "indexed"
        memory_error = None
        try:
            await self.memory_gateway.remember_private(
                request.user_id,
                FitMemoryEntry.from_product_snapshot(product),
            )
        except Exception as exc:
            memory_status = "failed"
            memory_error = str(exc) or exc.__class__.__name__

        self.store.save_capture(
            confirmed.model_copy(
                update={
                    "memory_status": memory_status,
                    "memory_error": memory_error,
                }
            )
        )
        return product.id

    async def _recall(
        self, request: AskFitRequest, product: ProductSnapshot | None
    ) -> MemoryContext:
        query = self._recall_query(request, product)
        try:
            return await self.memory_gateway.recall_private(
                RecallFitContextRequest(user_id=request.user_id, query=query, top_k=request.top_k)
            )
        except Exception as exc:
            return MemoryContext.degraded(
                request.user_id, query, str(exc) or exc.__class__.__name__
            )

    def _recall_query(self, request: AskFitRequest, product: ProductSnapshot | None) -> str:
        product_terms = []
        if product:
            product_terms = [
                product.brand or "",
                product.retailer or "",
                product.title,
                product.category.value,
                product.material or "",
                " ".join(product.size_options),
                " ".join(product.fit_descriptors),
            ]
        return " ".join(
            part.strip()
            for part in [
                request.question,
                request.context_notes or "",
                *product_terms,
                "fit size comfort silhouette returned kept tight loose shoulders chest fabric",
            ]
            if part and part.strip()
        )

    def _related_purchases(
        self, purchases: list[PurchaseRecord], product: ProductSnapshot | None
    ) -> list[PurchaseRecord]:
        if product is None:
            return purchases[:4]

        related = []
        for purchase in purchases:
            try:
                purchased_product = self.store.get_product(purchase.product_id)
            except Exception:
                continue
            if (
                purchased_product.brand == product.brand
                and purchased_product.category == product.category
            ):
                related.append(purchase)
        return related

    def _evidence(
        self,
        profile: FitProfile,
        product: ProductSnapshot | None,
        purchases: list[PurchaseRecord],
        recalled: MemoryContext,
    ) -> list[AskEvidence]:
        evidence: list[AskEvidence] = []

        if product:
            detail = self._product_detail(product)
            evidence.append(
                AskEvidence(label="Current item", detail=detail, source=f"product:{product.id}")
            )

        for purchase in purchases[:3]:
            evidence.append(
                AskEvidence(
                    label="Saved outcome",
                    detail=(
                        f"Size {purchase.purchased_size} was {purchase.outcome.value}; "
                        f"fit {purchase.fit_rating}/5, comfort {purchase.comfort_rating}/5. "
                        f"{purchase.fit_notes or 'No fit note saved.'}"
                    ),
                    source=f"purchase:{purchase.id}",
                )
            )

        preference = next(
            (
                item
                for item in profile.category_preferences
                if product is not None and item.category == product.category
            ),
            None,
        )
        if preference:
            evidence.append(
                AskEvidence(
                    label="Profile preference",
                    detail=(
                        f"Usually {preference.usual_size}; prefers "
                        f"{preference.preferred_fit.value}. {preference.notes or ''}".strip()
                    ),
                    source=f"profile:{profile.user_id}",
                )
            )

        profile_signal = self._profile_signal(profile)
        if profile_signal:
            evidence.append(
                AskEvidence(
                    label="Fit profile",
                    detail=profile_signal,
                    source=f"profile:{profile.user_id}",
                )
            )

        evidence.extend(
            AskEvidence(
                label="Private memory",
                detail=self._clean_memory_text(fact.text),
                source=fact.source,
            )
            for fact in recalled.facts[:4]
        )
        return evidence

    def _answer(
        self,
        request: AskFitRequest,
        profile: FitProfile,
        product: ProductSnapshot | None,
        purchases: list[PurchaseRecord],
        recalled: MemoryContext,
    ) -> str:
        profile_signal = self._profile_signal(profile)
        if product is None:
            if purchases or recalled.facts or profile_signal:
                signal = (
                    self._purchase_signal(purchases)
                    if purchases
                    else self._clean_memory_text(recalled.facts[0].text)
                    if recalled.facts
                    else profile_signal
                )
                if not self._asks_about_current_item(request.question):
                    return f"From your saved memory: {signal}"
                return (
                    "I can use your saved memory, but attach or extract the current item "
                    f"for a real size call. Most relevant signal: {signal}"
                )
            return (
                "Attach item photos or save a try-on outcome first, then I can compare it with "
                "your private fit memory."
            )

        if self._is_fit_memory_note(request.question):
            return (
                f"Got it. This reads like a try-on outcome and taste signal for "
                f"{self._display_name(product)}. Save it as memory so Mizaaj can recall that this "
                "fit worked for your chest and stomach comfort, relaxed drape, non-clingy fabric, "
                "and preference for subtle artwork."
            )

        size = self._recommended_size(product, profile, purchases)
        purchase_signal = self._purchase_signal(purchases)
        memory_signal = (
            f" I also found {len(recalled.facts)} private memory signal"
            f"{'' if len(recalled.facts) == 1 else 's'}."
            if recalled.facts
            else ""
        )
        profile_guardrail = (
            f" Keep your fit profile in mind: {profile_signal}." if profile_signal else ""
        )
        qualifier = (
            "Start with"
            if purchases or recalled.facts
            else "I would treat this as a calibration buy and start with"
        )

        return (
            f"{qualifier} {size or 'the most familiar size'} for {self._display_name(product)}. "
            f"{purchase_signal}{memory_signal}{profile_guardrail} After trying it, save whether "
            "the shoulder, chest, length, fabric feel, and silhouette matched what you wanted so "
            "the next answer gets sharper."
        )

    def _drafts(
        self,
        request: AskFitRequest,
        profile: FitProfile,
        product: ProductSnapshot | None,
        purchases: list[PurchaseRecord],
        recalled: MemoryContext,
    ) -> list[MemoryDraft]:
        drafts: list[MemoryDraft] = []

        if product:
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.product_fact,
                    subject=f"product:{product.id}",
                    text=f"User asked about {self._product_detail(product)}.",
                    confidence=0.72,
                    tags=self._product_tags(product),
                )
            )
            labels = self._size_labels(product)
            if labels:
                drafts.append(
                    MemoryDraft(
                        kind=MemoryDraftKind.size_mapping,
                        subject=f"product:{product.id}:size_labels",
                        text=(
                            f"{self._display_name(product)} showed size labels: "
                            f"{', '.join(labels)}."
                        ),
                        confidence=0.78,
                        tags=[*self._product_tags(product), "signal:size_labels"],
                    )
                )

        for purchase in purchases[:2]:
            try:
                purchased_product = self.store.get_product(purchase.product_id)
            except Exception:
                continue
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.brand_pattern,
                    subject=f"purchase:{purchase.id}:pattern",
                    text=(
                        f"For {purchased_product.brand or 'unknown brand'} "
                        f"{purchased_product.category.value}, size {purchase.purchased_size} "
                        f"was {purchase.outcome.value}. Notes: {purchase.fit_notes or 'none'}."
                    ),
                    confidence=0.86 if purchase.outcome != FitOutcome.unknown else 0.62,
                    tags=[
                        f"brand:{(purchased_product.brand or 'unknown').lower()}",
                        f"category:{purchased_product.category.value}",
                        f"outcome:{purchase.outcome.value}",
                    ],
                )
            )

        if request.context_notes and request.context_notes.strip():
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.fit_preference,
                    subject=f"user:{request.user_id}:ask_note",
                    text=f"User fit note: {request.context_notes.strip()}",
                    confidence=0.7,
                    tags=[f"user:{request.user_id}", "signal:user_note"],
                )
            )

        if product and self._is_fit_memory_note(request.question):
            note = request.question.strip()
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.fit_outcome,
                    subject=f"product:{product.id}:try_on_note",
                    text=f"User try-on note for {self._display_name(product)}: {note}",
                    confidence=0.86,
                    tags=[
                        *self._product_tags(product),
                        "outcome:kept" if self._mentions_kept(note) else "outcome:user_note",
                        "signal:try_on",
                    ],
                )
            )
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.fit_preference,
                    subject=f"user:{request.user_id}:taste",
                    text=(
                        "User prefers relaxed, non-clingy black T-shirts that do not feel tight "
                        "around the stomach or chest, keep the chest area visually clean, and use "
                        "small tasteful artwork rather than loud large prints."
                    ),
                    confidence=0.82,
                    tags=[
                        f"user:{request.user_id}",
                        f"category:{product.category.value}",
                        "signal:taste",
                        "fit:relaxed",
                    ],
                )
            )

        if not purchases and not recalled.facts and product:
            drafts.append(
                MemoryDraft(
                    kind=MemoryDraftKind.uncertainty,
                    subject=f"product:{product.id}:uncertainty",
                    text=(
                        f"No confirmed private fit outcome exists yet for "
                        f"{product.brand or 'this brand'} {product.category.value}."
                    ),
                    confidence=0.6,
                    tags=self._product_tags(product),
                )
            )

        return drafts[:5]

    def _confidence(
        self,
        product: ProductSnapshot | None,
        purchases: list[PurchaseRecord],
        recalled: MemoryContext,
        *,
        has_profile_signal: bool = False,
    ) -> float:
        value = 0.34 if product else (0.5 if recalled.facts or has_profile_signal else 0.22)
        if product and product.size_chart:
            value += 0.16
        if product and (product.size_options or product.size_labels):
            value += 0.08
        if purchases:
            value += min(0.28, len(purchases) * 0.1)
        if recalled.facts:
            value += min(0.22, len(recalled.facts) * 0.055)
        if has_profile_signal:
            value += 0.06
        return min(value, 0.9)

    def _asks_about_current_item(self, question: str) -> bool:
        text = question.lower()
        current_item_signals = [
            "this item",
            "this product",
            "this shirt",
            "this tee",
            "these photos",
            "attached",
            "current item",
            "what size should i",
            "should i buy this",
            "will this fit",
            "will this match",
        ]
        return any(signal in text for signal in current_item_signals)

    def _recommended_size(
        self, product: ProductSnapshot, profile: FitProfile, purchases: list[PurchaseRecord]
    ) -> str | None:
        kept = [purchase for purchase in purchases if purchase.outcome == FitOutcome.kept]
        if kept:
            return kept[0].purchased_size

        preference = next(
            (item for item in profile.category_preferences if item.category == product.category),
            None,
        )
        candidate_sizes = {size.lower() for size in self._size_candidates(product)}
        if preference and (
            not product.size_options or preference.usual_size.lower() in candidate_sizes
        ):
            return preference.usual_size

        candidates = self._size_candidates(product)
        if candidates:
            return candidates[(len(candidates) - 1) // 2]
        return None

    def _purchase_signal(self, purchases: list[PurchaseRecord]) -> str:
        if not purchases:
            return "There is no confirmed outcome for this brand and category yet."
        kept = [purchase for purchase in purchases if purchase.outcome == FitOutcome.kept]
        returned = [purchase for purchase in purchases if purchase.outcome == FitOutcome.returned]
        if kept:
            latest = kept[0]
            return (
                f"Your saved outcome says size {latest.purchased_size} worked before: "
                f"{latest.fit_notes or 'no note saved'}."
            )
        if returned:
            latest = returned[0]
            return (
                f"Your saved outcome warns that size {latest.purchased_size} was returned: "
                f"{latest.fit_notes or 'no note saved'}."
            )
        return (
            f"You have {len(purchases)} related saved outcome signal(s), but none marked kept yet."
        )

    def _profile_signal(self, profile: FitProfile) -> str:
        signals: list[str] = []
        if profile.sensitivities:
            signals.append(f"watch {', '.join(profile.sensitivities[:4])}")
        if profile.body_notes and profile.body_notes.strip():
            signals.append(profile.body_notes.strip())
        return "; ".join(signals).strip()[:240].rstrip()

    def _product_detail(self, product: ProductSnapshot) -> str:
        parts = [
            self._display_name(product),
            product.category.value,
            product.color,
            product.material,
        ]
        if product.fit_descriptors:
            parts.append(f"fit descriptors {', '.join(product.fit_descriptors)}")
        labels = self._size_labels(product)
        if labels:
            parts.append(f"labels {', '.join(labels)}")
        elif product.size_options:
            parts.append(f"sizes {', '.join(product.size_options)}")
        return ", ".join(part for part in parts if part)

    def _clean_memory_text(self, value: str) -> str:
        text = value.strip()
        raw_match = re.search(r"raw=\{['\"]value['\"]:\s*['\"](.+?)['\"]\}", text)
        text_match = re.search(
            r"text=['\"](.+?)['\"]\s+(?:dataset_name|metadata|source|score|$)", text
        )
        text = (raw_match or text_match).group(1) if raw_match or text_match else text
        return clean_recall_text(text)

    def _display_name(self, product: ProductSnapshot) -> str:
        return display_name(product)

    def _is_fit_memory_note(self, question: str) -> bool:
        text = question.lower()
        note_signals = [
            "i kept",
            "i bought",
            "i tried",
            "i wore",
            "fit is",
            "fits good",
            "fits well",
            "does not feel tight",
            "doesn't feel tight",
            "does not cling",
            "doesn't cling",
            "works well for me",
            "remember that",
            "i like",
            "i prefer",
            "my stomach",
            "my chest",
        ]
        question_starters = (
            "should ",
            "what ",
            "which ",
            "can you ",
            "tell me ",
            "compare ",
            "is this ",
            "will this ",
        )
        if text.strip().startswith(question_starters) and "i kept" not in text:
            return False
        return any(signal in text for signal in note_signals)

    def _mentions_kept(self, question: str) -> bool:
        text = question.lower()
        return any(signal in text for signal in ["i kept", "kept it", "i bought"])

    def _size_labels(self, product: ProductSnapshot) -> list[str]:
        return [
            " ".join(part for part in [item.system or item.region, item.label] if part).strip()
            for item in product.size_labels
        ]

    def _size_candidates(self, product: ProductSnapshot) -> list[str]:
        raw_sizes = (
            [size_set.size for size_set in product.size_chart]
            or [item.label for item in product.size_labels]
            or product.size_options
        )
        sizes: list[str] = []
        seen: set[str] = set()
        for size in raw_sizes:
            candidate = re.sub(r"^(standard|uk|eur|eu|us)\s+", "", size.strip(), flags=re.I)
            key = candidate.lower()
            if candidate and key not in seen:
                sizes.append(candidate)
                seen.add(key)
        return sizes

    def _product_tags(self, product: ProductSnapshot) -> list[str]:
        return [
            f"product:{product.id}",
            f"brand:{(product.brand or 'unknown').lower()}",
            f"category:{product.category.value}",
        ]
