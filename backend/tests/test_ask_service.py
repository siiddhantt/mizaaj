from uuid import UUID

import pytest

from app.core.errors import ForbiddenError
from app.domain.ask.schemas import (
    AskFitRequest,
    ConversationRole,
    ConversationTurn,
    MemoryDraft,
    MemoryDraftKind,
    OutcomeDraft,
    RememberMemoryDraftsRequest,
)
from app.domain.ask.service import AskFitService
from app.domain.captures.schemas import CaptureResponse
from app.domain.common import ClothingCategory
from app.domain.memory.schemas import FitMemoryEntry, MemoryContextFact, RecallFitContextRequest
from app.domain.products.schemas import ProductDraft, ProductSnapshot, SizeLabel
from app.domain.profiles.schemas import FitProfileUpdate
from app.domain.reasoning.schemas import GroundedReasoningResult
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubAtlasGateway, StubMemoryGateway, StubReasoningGateway

OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000002")


@pytest.mark.asyncio
async def test_ask_returns_private_evidence_and_memory_drafts():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0]
    await memory.remember_private(
        LOCAL_USER_ID,
        FitMemoryEntry(
            subject="purchase:uniqlo",
            text="Uniqlo shirt in M had good shoulder width and relaxed chest.",
            tags=["brand:uniqlo", "category:shirt", "outcome:kept"],
        ),
    )

    response = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="What size should I buy and what should I remember?",
            context_notes="I want this to drape without sticking to my chest.",
        )
    )

    assert "Start with M" in response.answer
    assert response.evidence
    assert any(item.label == "Private memory" for item in response.evidence)
    assert any(draft.kind == "fit_preference" for draft in response.memory_drafts)
    assert any("drape" in draft.text for draft in response.memory_drafts)


@pytest.mark.asyncio
async def test_ask_answers_saved_taste_without_current_item_warning():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    await memory.remember_private(
        LOCAL_USER_ID,
        FitMemoryEntry(
            subject="taste:black_tee",
            text=(
                "User prefers relaxed non-clingy black T-shirts that do not feel tight "
                "around the stomach or chest and use small tasteful artwork."
            ),
            tags=["category:tshirt", "signal:taste"],
        ),
    )

    response = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            question="What are my non-negotiables for another black tee?",
        )
    )

    assert response.answer.startswith("From your saved memory:")
    assert "attach or extract" not in response.answer.lower()
    assert response.confidence >= 0.5


@pytest.mark.asyncio
async def test_ask_uses_profile_context_without_attached_item():
    store = InMemoryStore()
    memory = StubMemoryGateway()
    store.update_profile(
        LOCAL_USER_ID,
        FitProfileUpdate(
            display_name="Sid",
            body_notes="Prefers subtle artwork, relaxed drape, and no chest or stomach cling.",
            sensitivities=["chest cling", "stomach cling", "fabric feels flimsy"],
        ),
    )

    response = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            question="What should I watch for when buying another black tee?",
        )
    )

    assert response.answer.startswith("From your saved memory:")
    assert "subtle artwork" in response.answer
    assert "chest cling" in response.answer
    assert response.confidence >= 0.5


@pytest.mark.asyncio
async def test_ask_labels_atlas_separately_from_private_memory():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0]
    await memory.remember_private(
        LOCAL_USER_ID,
        FitMemoryEntry(
            subject="private:uniqlo",
            text="Private memory says Uniqlo M worked for shoulder width.",
            tags=["brand:uniqlo", "category:shirt"],
        ),
    )
    atlas = StubAtlasGateway(
        [
            MemoryContextFact(
                text=(
                    "Uniqlo Oxford shirt. Public Atlas evidence: material cotton; "
                    "fit regular. Non-personal interpretation: check sleeve length."
                ),
                source="mizaaj_atlas:uniqlo_oxford",
                score=4,
            )
        ]
    )

    response = await AskFitService(store, memory, atlas).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="What should I check before buying this shirt?",
        )
    )

    labels = {item.label for item in response.evidence}
    assert "Private memory" in labels
    assert "Mizaaj Atlas" in labels
    assert any(item.source.startswith("mizaaj_atlas") for item in response.evidence)
    assert any(
        item.detail.startswith("Same-brand Atlas reference, not the exact product")
        for item in response.evidence
        if item.label == "Mizaaj Atlas"
    )
    assert "Public Atlas evidence adds" in response.answer
    assert atlas.queries


@pytest.mark.asyncio
async def test_ask_summarizes_atlas_size_charts_without_truncated_rows():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0].model_copy(
        update={
            "sku": "433665",
            "url": "https://www.uniqlo.com/us/en/products/433665",
        }
    )
    store.save_product(product)
    atlas = StubAtlasGateway(
        [
            MemoryContextFact(
                text=(
                    "Size chart (Uniqlo Oxford shirt). S: chest 104 cm, length 72 cm, "
                    "shoulder 43 cm. M: chest 108 cm, length 74 cm, shoulder 45 cm. "
                    "L: chest 112 cm, length 76 cm, shoulder 47 cm. Private outcomes "
                    "should override public chart evidence."
                ),
                source="mizaaj_atlas:uniqlo_oxford_size_chart",
                score=4,
            )
        ]
    )

    response = await AskFitService(store, memory, atlas).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="What size should I start with and what should I measure?",
        )
    )

    assert "Atlas found" in response.answer
    assert "size chart" in response.answer
    assert "for S-L" in response.answer
    assert "chest, length, shoulder measurements" in response.answer
    assert "Private outcomes should override" not in response.answer
    atlas_evidence = [item for item in response.evidence if item.label == "Mizaaj Atlas"]
    assert atlas_evidence
    assert "M: chest 108 cm" in atlas_evidence[0].detail
    assert atlas.queries
    assert "433665" in atlas.queries[0].query
    assert "https://www.uniqlo.com/us/en/products/433665" in atlas.queries[0].query
    assert "size chart measurements" in atlas.queries[0].query


@pytest.mark.asyncio
async def test_ask_uses_unconfirmed_capture_as_temporary_item_context():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=LOCAL_USER_ID,
            source_type="upload",
            product_draft=ProductDraft(
                brand="The Bear House",
                title="Drop shoulder t-shirt",
                category=ClothingCategory.shirt,
                material="cotton",
                size_options=["M", "L"],
                fit_descriptors=["drop shoulder", "relaxed"],
            ),
        )
    )

    response = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            capture_id=capture.id,
            question="Should I buy M or L?",
        )
    )

    assert "The Bear House - Drop shoulder t-shirt" in response.answer
    assert any(item.label == "Current item" for item in response.evidence)
    assert any("drop shoulder" in item.detail for item in response.evidence)

    repeated = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            capture_id=capture.id,
            question="What about the same shirt's sleeves?",
        )
    )
    first_source = next(item.source for item in response.evidence if item.label == "Current item")
    repeated_source = next(
        item.source for item in repeated.evidence if item.label == "Current item"
    )
    assert repeated_source == first_source


@pytest.mark.asyncio
async def test_ask_uses_grounded_reasoning_with_conversation_and_evidence():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0]
    reasoner = StubReasoningGateway(
        GroundedReasoningResult(
            answer="Your saved M outcome is the strongest signal.",
            confidence=0.83,
            used_evidence_sources=[f"product:{product.id}"],
            memory_drafts=[
                MemoryDraft(
                    kind=MemoryDraftKind.fit_preference,
                    subject=f"user:{LOCAL_USER_ID}:fit_preference",
                    text="User explicitly prefers relaxed shoulders.",
                )
            ],
            outcome_draft=OutcomeDraft(
                purchased_size="M",
                outcome="kept",
                fit_notes="Relaxed shoulders worked well.",
            ),
        )
    )
    conversation = [
        ConversationTurn(role=ConversationRole.user, content="I tried the shirt yesterday."),
        ConversationTurn(role=ConversationRole.assistant, content="How did the shoulders feel?"),
    ]

    response = await AskFitService(store, memory, reasoning_gateway=reasoner).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="They felt relaxed, and I kept M.",
            conversation=conversation,
        )
    )

    assert response.reasoning_status == "grounded"
    assert response.answer == "Your saved M outcome is the strongest signal."
    assert response.outcome_draft is not None
    assert response.outcome_draft.purchased_size == "M"
    assert reasoner.requests[0].conversation == conversation
    assert any(item.label == "Current item" for item in reasoner.requests[0].evidence)


@pytest.mark.asyncio
async def test_ask_does_not_propose_outcome_from_recalled_history_alone():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0]
    reasoner = StubReasoningGateway(
        GroundedReasoningResult(
            answer="Your earlier outcome is useful evidence.",
            confidence=0.8,
            outcome_draft=OutcomeDraft(
                purchased_size="M",
                outcome="kept",
                fit_notes="Recalled from an earlier memory.",
            ),
        )
    )

    response = await AskFitService(store, memory, reasoning_gateway=reasoner).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="Should I keep this one?",
        )
    )

    assert response.outcome_draft is None


@pytest.mark.asyncio
async def test_ask_memory_drafts_format_regional_sizes_without_duplicate_prefixes():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=LOCAL_USER_ID,
            source_type="upload",
            product_draft=ProductDraft(
                brand="The Bear House",
                title="Drop shoulder t-shirt",
                category=ClothingCategory.tshirt,
                color="Black",
                size_options=["UK L", "EUR L"],
                size_labels=[
                    SizeLabel(label="L", system="UK", region="UK"),
                    SizeLabel(label="L", system="EUR", region="Europe"),
                ],
            ),
        )
    )

    response = await AskFitService(store, memory).ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            capture_id=capture.id,
            question="What should I remember?",
        )
    )

    text = " ".join(draft.text for draft in response.memory_drafts)
    assert "UK L" in text
    assert "EUR L" in text
    assert "UK UK L" not in text
    assert "Europe EUR L" not in text


@pytest.mark.asyncio
async def test_remember_ask_drafts_indexes_selected_memory():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[0]
    service = AskFitService(store, memory)
    response = await service.ask(
        AskFitRequest(
            user_id=LOCAL_USER_ID,
            product_id=product.id,
            question="What should I remember after trying this?",
            context_notes="Size M fit well, but the sleeves were slightly long.",
        )
    )

    remembered = await service.remember_drafts(
        RememberMemoryDraftsRequest(
            user_id=LOCAL_USER_ID,
            drafts=response.memory_drafts,
            question=response.question,
            answer=response.answer,
            product_id=product.id,
            evidence=response.evidence,
            recalled_facts=response.recalled_facts,
        )
    )

    assert remembered.memory_status == "indexed"
    assert remembered.memory_record is not None
    assert store.list_saved_memories(LOCAL_USER_ID)[0].question == response.question
    recalled = await memory.recall_private(
        RecallFitContextRequest(
            user_id=LOCAL_USER_ID,
            query="sleeves were slightly long",
        )
    )
    assert any("sleeves" in fact.text for fact in recalled.facts)


@pytest.mark.asyncio
async def test_ask_rejects_capture_owned_by_another_user():
    store = InMemoryStore()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=OTHER_USER_ID,
            source_type="upload",
            product_draft=ProductDraft(title="Foreign capture"),
        )
    )

    with pytest.raises(ForbiddenError):
        await AskFitService(store, memory).ask(
            AskFitRequest(
                user_id=LOCAL_USER_ID,
                capture_id=capture.id,
                question="Can I use this?",
            )
        )


@pytest.mark.asyncio
async def test_ask_rejects_product_owned_by_another_user():
    store = InMemoryStore()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=OTHER_USER_ID,
            source_type="manual",
            product_draft=ProductDraft(title="Foreign product"),
        )
    )
    product = store.save_product(
        ProductSnapshot(
            title="Foreign product",
            source_capture_id=capture.id,
        )
    )

    with pytest.raises(ForbiddenError):
        await AskFitService(store, memory).ask(
            AskFitRequest(
                user_id=LOCAL_USER_ID,
                product_id=product.id,
                question="What size?",
            )
        )


@pytest.mark.asyncio
async def test_remember_rejects_foreign_capture_reference():
    store = InMemoryStore()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=OTHER_USER_ID,
            source_type="upload",
            product_draft=ProductDraft(title="Foreign capture"),
        )
    )

    with pytest.raises(ForbiddenError):
        await AskFitService(store, memory).remember_drafts(
            RememberMemoryDraftsRequest(
                user_id=LOCAL_USER_ID,
                capture_id=capture.id,
                question="Remember this",
                answer="Nope",
                drafts=[],
            )
        )
