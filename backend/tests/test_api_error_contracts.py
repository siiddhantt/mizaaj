from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubExtractionGateway, StubMemoryGateway


def test_empty_ask_question_returns_validation_error():
    client = _client()

    response = client.post(
        "/api/v1/ask",
        json={"user_id": str(LOCAL_USER_ID), "question": ""},
    )

    assert response.status_code == 422


def test_purchase_with_unknown_product_returns_not_found():
    client = _client()

    response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(uuid4()),
            "purchased_size": "M",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_delete_user_data_is_idempotent_after_first_delete():
    client = _client()

    first_response = client.delete(f"/api/v1/memory/users/{LOCAL_USER_ID}/app-data")
    second_response = client.delete(f"/api/v1/memory/users/{LOCAL_USER_ID}/app-data")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == {
        "profile_deleted": False,
        "captures_deleted": 0,
        "products_deleted": 0,
        "purchases_deleted": 0,
        "saved_memories_deleted": 0,
        "cognee_memory_deleted": True,
    }


def _client() -> TestClient:
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    app.dependency_overrides[get_store] = lambda: InMemoryStore()
    app.dependency_overrides[get_memory_gateway] = lambda: StubMemoryGateway()
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    return TestClient(app)
