from uuid import UUID

from fastapi.testclient import TestClient

from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import FailingMemoryGateway, StubExtractionGateway, StubMemoryGateway


def test_confirmed_capture_is_recallable_and_forgettable():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    client = TestClient(app)

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": [
                "Zara linen blend relaxed shirt. Sizes S M L XL. 55% linen 45% cotton."
            ],
            "assets": [],
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()
    accepted_claim_ids = [claim["id"] for claim in capture["product_draft"]["extracted_claims"]]
    assert accepted_claim_ids

    confirm_response = client.post(
        f"/api/v1/captures/{capture['id']}/confirm",
        json={
            "product_draft": capture["product_draft"],
            "accepted_claim_ids": accepted_claim_ids,
        },
    )
    assert confirm_response.status_code == 200
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["memory_status"] == "indexed"
    assert confirmed["product_snapshot"]["extracted_claims"]

    recall_response = client.post(
        "/api/v1/memory/recall",
        json={
            "user_id": str(LOCAL_USER_ID),
            "query": "Zara linen material captured product",
            "top_k": 5,
        },
    )
    assert recall_response.status_code == 200
    assert recall_response.json()["facts"]

    forget_response = client.delete(f"/api/v1/memory/users/{LOCAL_USER_ID}")
    assert forget_response.status_code == 200

    forgotten_response = client.post(
        "/api/v1/memory/recall",
        json={
            "user_id": str(UUID(str(LOCAL_USER_ID))),
            "query": "Zara linen material captured product",
            "top_k": 5,
        },
    )
    assert forgotten_response.status_code == 200
    assert forgotten_response.json()["facts"] == []


def test_capture_confirmation_persists_product_when_memory_indexing_fails():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: FailingMemoryGateway()
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    client = TestClient(app)

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara cotton shirt. Sizes S M L."],
            "assets": [],
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
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["memory_status"] == "failed"
    assert confirmed["memory_error"] == "memory unavailable"
    assert confirmed["product_snapshot"]["id"] in {
        str(product.id) for product in store.list_products()
    }


def test_capture_api_lists_gets_and_deletes_unconfirmed_capture():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: StubMemoryGateway()
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara cotton shirt. Sizes S M L."],
            "assets": [],
        },
    )
    assert create_response.status_code == 200
    capture = create_response.json()

    list_response = client.get(f"/api/v1/captures/users/{LOCAL_USER_ID}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [capture["id"]]

    get_response = client.get(f"/api/v1/captures/{capture['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == capture["id"]

    delete_response = client.delete(f"/api/v1/captures/{capture['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == capture["id"]

    list_after_delete = client.get(f"/api/v1/captures/users/{LOCAL_USER_ID}")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


def test_confirmed_capture_delete_removes_product_and_rebuilds_memory():
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

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara linen shirt. Sizes S M L."],
            "assets": [],
        },
    )
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
    confirmed = confirm_response.json()
    product_id = confirmed["product_snapshot"]["id"]

    recall_before = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "Zara linen", "top_k": 3},
    )
    assert recall_before.status_code == 200
    assert recall_before.json()["facts"]

    delete_response = client.delete(f"/api/v1/captures/{capture['id']}")
    assert delete_response.status_code == 200
    assert product_id not in {str(product.id) for product in store.list_products()}

    recall_after = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "Zara linen", "top_k": 3},
    )
    assert recall_after.status_code == 200
    assert recall_after.json()["facts"] == []


def test_confirmed_capture_delete_is_blocked_when_purchase_exists():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: StubMemoryGateway()
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    client = TestClient(app)

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara linen shirt. Sizes S M L."],
            "assets": [],
        },
    )
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
    product_id = confirm_response.json()["product_snapshot"]["id"]

    purchase_response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": product_id,
            "purchased_size": "M",
            "outcome": "kept",
        },
    )
    assert purchase_response.status_code == 200

    delete_response = client.delete(f"/api/v1/captures/{capture['id']}")
    assert delete_response.status_code == 403
