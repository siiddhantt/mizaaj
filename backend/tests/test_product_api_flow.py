from fastapi.testclient import TestClient

from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubExtractionGateway, StubMemoryGateway


def test_delete_product_from_confirmed_capture_demotes_capture_and_rebuilds_memory():
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
    assert confirm_response.status_code == 200
    product_id = confirm_response.json()["product_snapshot"]["id"]

    delete_response = client.delete(f"/api/v1/products/{product_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == product_id

    capture_after_delete = client.get(f"/api/v1/captures/{capture['id']}")
    assert capture_after_delete.status_code == 200
    assert capture_after_delete.json()["confirmed"] is False
    assert capture_after_delete.json()["product_snapshot"] is None


def test_delete_product_is_blocked_when_purchase_exists():
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

    delete_response = client.delete(f"/api/v1/products/{product_id}")
    assert delete_response.status_code == 403
