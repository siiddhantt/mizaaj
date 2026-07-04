from uuid import UUID

import pytest

from app.core.errors import ForbiddenError
from app.domain.ask.schemas import AskFitRequest, RememberMemoryDraftsRequest
from app.domain.ask.service import AskFitService
from app.domain.captures.schemas import CaptureResponse
from app.domain.common import ClothingCategory
from app.domain.memory.schemas import FitMemoryEntry, RecallFitContextRequest
from app.domain.products.schemas import ProductDraft, ProductSnapshot, SizeLabel
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubMemoryGateway

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
