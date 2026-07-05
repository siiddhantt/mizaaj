from collections import defaultdict
from uuid import UUID

from app.domain.atlas.schemas import AtlasContext, AtlasRecallRequest
from app.domain.captures.schemas import CaptureCreate
from app.domain.claims import ExtractedClaim
from app.domain.common import ClothingCategory
from app.domain.memory.schemas import (
    FitMemoryEntry,
    ForgetScope,
    MemoryContext,
    MemoryContextFact,
    RecallFitContextRequest,
)
from app.domain.products.schemas import ProductDraft


class StubExtractionGateway:
    async def extract_product(self, capture: CaptureCreate) -> ProductDraft:
        text = " ".join(capture.text_blocks + [capture.user_notes or ""]).strip()
        source = capture.page_url or (capture.assets[0].path if capture.assets else "manual_input")
        sizes = ["S", "M", "L", "XL"]
        claims = [
            ExtractedClaim(
                subject="Zara linen shirt",
                predicate="category",
                value=ClothingCategory.shirt.value,
                source=source,
                confidence=0.8,
            ),
            ExtractedClaim(
                subject="Zara linen shirt",
                predicate="material",
                value="linen, cotton",
                source=source,
                confidence=0.82,
            ),
            ExtractedClaim(
                subject="Zara linen shirt",
                predicate="available_sizes",
                value=", ".join(sizes),
                source=source,
                confidence=0.78,
            ),
        ]
        return ProductDraft(
            brand="Zara" if "zara" in text.lower() else None,
            title=text[:90] or "Captured item",
            url=capture.page_url,
            category=ClothingCategory.shirt,
            material="linen, cotton",
            size_options=sizes,
            extracted_claims=claims,
        )


class StubMemoryGateway:
    def __init__(self):
        self._entries: dict[UUID, list[FitMemoryEntry]] = defaultdict(list)

    async def remember_private(self, user_id: UUID, entry: FitMemoryEntry) -> None:
        self._entries[user_id].append(entry)

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        terms = {part.lower() for part in query.query.split() if len(part) > 2}
        scored = []
        for entry in self._entries.get(query.user_id, []):
            haystack = " ".join([entry.text, " ".join(entry.tags)]).lower()
            score = sum(1 for term in terms if term in haystack)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        facts = [
            MemoryContextFact(text=entry.text, source=entry.source_id or entry.subject, score=score)
            for score, entry in scored[: query.top_k]
        ]
        return MemoryContext(user_id=query.user_id, query=query.query, facts=facts)

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None:
        if scope == ForgetScope.all_private:
            self._entries.pop(user_id, None)
            return
        prefix = f"source:{scope.value.rstrip('s')}"
        self._entries[user_id] = [
            entry for entry in self._entries.get(user_id, []) if prefix not in entry.tags
        ]


class StubAtlasGateway:
    def __init__(self, facts: list[MemoryContextFact] | None = None):
        self.facts = facts or []
        self.queries: list[AtlasRecallRequest] = []

    async def recall_public(self, request: AtlasRecallRequest) -> AtlasContext:
        self.queries.append(request)
        return AtlasContext(query=request.query, facts=self.facts[: request.top_k])


class FailingMemoryGateway:
    async def remember_private(self, user_id: UUID, entry: FitMemoryEntry) -> None:
        raise RuntimeError("memory unavailable")

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        return MemoryContext(user_id=query.user_id, query=query.query, facts=[])

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None:
        return None


class FailingRecallMemoryGateway(StubMemoryGateway):
    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        raise TimeoutError("memory recall timed out")
