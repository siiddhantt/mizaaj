from uuid import UUID

import pytest

from app.domain.memory.schemas import FitMemoryEntry
from app.domain.recommendations.schemas import RecommendationRequest
from app.domain.recommendations.service import RecommendationService
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubMemoryGateway


@pytest.mark.asyncio
async def test_recommendation_uses_private_memory_context():
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    product = store.list_products()[1]
    await memory.remember_private(
        LOCAL_USER_ID,
        FitMemoryEntry(
            subject="purchase:test",
            text="Zara shirt in M was returned because the chest felt tight.",
            tags=["brand:zara", "category:shirt", "outcome:returned"],
        ),
    )

    response = await RecommendationService(store, memory).recommend(
        RecommendationRequest(user_id=LOCAL_USER_ID, product_id=product.id)
    )

    assert response.recommended_size == "M"
    assert response.confidence > 0.5
    assert any("tight" in risk.lower() for risk in response.risks)


def test_seeded_store_has_local_user():
    store = InMemoryStore.seeded()
    profile = store.get_profile(UUID("00000000-0000-4000-8000-000000000001"))

    assert profile.display_name == "Sid"
