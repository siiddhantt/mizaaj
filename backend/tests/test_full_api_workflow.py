from fastapi.testclient import TestClient

from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubExtractionGateway, StubMemoryGateway


def test_full_private_fit_memory_workflow():
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

    auth_response = client.get("/api/v1/auth/me")
    assert auth_response.status_code == 200
    assert auth_response.json()["user_id"] == str(LOCAL_USER_ID)

    profile_response = client.put(
        f"/api/v1/profiles/{LOCAL_USER_ID}",
        json={
            "display_name": "Sid",
            "sensitivities": ["clingy fabric", "tight chest"],
            "category_preferences": [
                {
                    "category": "shirt",
                    "usual_size": "M",
                    "preferred_fit": "relaxed",
                    "notes": "Prefers shoulder room and a soft drape.",
                }
            ],
        },
    )
    assert profile_response.status_code == 200

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "upload",
            "text_blocks": [
                "Zara linen blend relaxed shirt. Sizes S M L XL. 55% linen 45% cotton."
            ],
            "assets": [
                {
                    "path": "users/local/captures/tag.jpg",
                    "mime_type": "image/jpeg",
                    "original_name": "tag.jpg",
                    "public_url": "https://example.com/tag.jpg",
                },
                {
                    "path": "users/local/captures/size-chart.jpg",
                    "mime_type": "image/jpeg",
                    "original_name": "size-chart.jpg",
                    "public_url": "https://example.com/size-chart.jpg",
                },
            ],
            "user_notes": "Avoid clingy fabric around the chest.",
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()
    assert capture["confirmed"] is False
    assert capture["product_draft"]["extracted_claims"]

    first_ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "capture_id": capture["id"],
            "question": "Should I buy this, and what should Mizaaj remember?",
            "context_notes": "Avoid clingy fabric around the chest.",
        },
    )
    assert first_ask_response.status_code == 200
    first_ask = first_ask_response.json()
    assert first_ask["answer"]
    assert first_ask["memory_drafts"]
    assert any(item["label"] == "Current item" for item in first_ask["evidence"])

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "capture_id": capture["id"],
            "drafts": first_ask["memory_drafts"],
            "question": first_ask["question"],
            "answer": first_ask["answer"],
            "evidence": first_ask["evidence"],
            "recalled_facts": first_ask["recalled_facts"],
        },
    )
    assert remember_response.status_code == 200
    saved_memory = remember_response.json()["memory_record"]
    assert saved_memory["remembered"]

    recall_response = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "clingy fabric chest", "top_k": 5},
    )
    assert recall_response.status_code == 200
    assert recall_response.json()["facts"]

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
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["memory_status"] == "indexed"
    product_id = confirmed["product_snapshot"]["id"]

    product_ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": product_id,
            "question": "What size should I start with now?",
        },
    )
    assert product_ask_response.status_code == 200
    product_ask = product_ask_response.json()
    assert product_ask["confidence"] > first_ask["confidence"]
    assert any(item["label"] == "Private memory" for item in product_ask["evidence"])

    purchase_response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": product_id,
            "purchased_size": "M",
            "outcome": "kept",
            "fit_rating": 5,
            "comfort_rating": 4,
            "silhouette_rating": 5,
            "fit_notes": "Size M had enough shoulder room and did not cling.",
        },
    )
    assert purchase_response.status_code == 200
    purchase = purchase_response.json()

    updated_purchase_response = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        json={
            "comfort_rating": 5,
            "fit_notes": "Size M was kept; shoulder room and drape were ideal.",
        },
    )
    assert updated_purchase_response.status_code == 200
    assert updated_purchase_response.json()["comfort_rating"] == 5

    saved_outcome_ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": product_id,
            "question": "What did my try-on outcome prove?",
        },
    )
    assert saved_outcome_ask_response.status_code == 200
    assert any(
        item["label"] == "Saved outcome" for item in saved_outcome_ask_response.json()["evidence"]
    )

    delete_purchase_response = client.delete(f"/api/v1/purchases/{purchase['id']}")
    assert delete_purchase_response.status_code == 200
    assert client.get(f"/api/v1/purchases/user/{LOCAL_USER_ID}").json() == []

    delete_memory_response = client.delete(f"/api/v1/ask/memories/{saved_memory['id']}")
    assert delete_memory_response.status_code == 200
    assert client.get(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}").json() == []

    delete_user_response = client.delete(f"/api/v1/memory/users/{LOCAL_USER_ID}/app-data")
    assert delete_user_response.status_code == 200
    assert delete_user_response.json()["captures_deleted"] == 1
    assert delete_user_response.json()["products_deleted"] == 1
    assert client.get(f"/api/v1/captures/users/{LOCAL_USER_ID}").json() == []
    assert client.get("/api/v1/products").json() == []
