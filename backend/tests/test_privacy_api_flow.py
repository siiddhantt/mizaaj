from fastapi.testclient import TestClient

from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubExtractionGateway, StubMemoryGateway


def test_delete_user_data_clears_app_rows_and_private_memory():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    client = TestClient(app)

    profile_response = client.put(
        f"/api/v1/profiles/{LOCAL_USER_ID}",
        json={"display_name": "Sid", "sensitivities": ["scratchy wool"]},
    )
    assert profile_response.status_code == 200

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara linen shirt in size M"],
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()

    confirm_response = client.post(
        f"/api/v1/captures/{capture['id']}/confirm",
        json={
            "product_draft": capture["product_draft"],
            "accepted_claim_ids": [
                claim["id"] for claim in capture["product_draft"]["extracted_claims"]
            ],
        },
    )
    assert confirm_response.status_code == 200
    product = confirm_response.json()["product_snapshot"]

    purchase_response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": product["id"],
            "purchased_size": "M",
            "outcome": "kept",
            "fit_notes": "Great shoulder line.",
        },
    )
    assert purchase_response.status_code == 200

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "question": "What should Mizaaj remember?",
            "answer": "Remember that scratchy wool is bad.",
            "drafts": [
                {
                    "kind": "fit_preference",
                    "subject": "fabric feel",
                    "text": "Sid avoids scratchy wool.",
                    "confidence": 0.9,
                    "tags": ["fabric"],
                }
            ],
        },
    )
    assert remember_response.status_code == 200

    delete_response = client.delete(f"/api/v1/memory/users/{LOCAL_USER_ID}/app-data")
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "profile_deleted": True,
        "captures_deleted": 1,
        "products_deleted": 1,
        "purchases_deleted": 1,
        "saved_memories_deleted": 1,
        "cognee_memory_deleted": True,
    }

    assert client.get(f"/api/v1/captures/users/{LOCAL_USER_ID}").json() == []
    assert client.get(f"/api/v1/purchases/user/{LOCAL_USER_ID}").json() == []
    assert client.get("/api/v1/products").json() == []
    assert client.get(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}").json() == []

    recall_response = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "scratchy wool", "top_k": 5},
    )
    assert recall_response.status_code == 200
    assert recall_response.json()["facts"] == []
