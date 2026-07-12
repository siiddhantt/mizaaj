from uuid import UUID

from fastapi.testclient import TestClient

from app.core.dependencies import get_memory_gateway, get_store
from app.domain.captures.schemas import CaptureResponse
from app.domain.common import FitOutcome
from app.domain.products.schemas import ProductDraft, ProductSnapshot
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubMemoryGateway

OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000002")


def test_purchase_rejects_product_owned_by_another_user():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    memory = StubMemoryGateway()
    capture = store.save_capture(
        CaptureResponse(
            user_id=OTHER_USER_ID,
            source_type="manual",
            product_draft=ProductDraft(title="Private product"),
        )
    )
    product = store.save_product(
        ProductSnapshot(title="Private product", source_capture_id=capture.id)
    )
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = TestClient(app)

    response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "purchased_size": "M",
            "outcome": "kept",
        },
    )

    assert response.status_code == 403


def test_purchase_api_crud_rebuilds_private_memory():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = TestClient(app)

    product = InMemoryStore.seeded().list_products()[0]
    store.save_product(product)

    create_response = client.post(
        "/api/v1/purchases",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "purchased_size": "M",
            "outcome": "kept",
            "fit_rating": 5,
            "comfort_rating": 4,
            "silhouette_rating": 4,
            "fit_notes": "Shoulders felt clean and sleeves were fine.",
        },
    )
    assert create_response.status_code == 200
    purchase = create_response.json()

    get_response = client.get(f"/api/v1/purchases/{purchase['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["purchased_size"] == "M"

    recall_before = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "sleeves fine", "top_k": 3},
    )
    assert recall_before.status_code == 200
    assert recall_before.json()["facts"]

    update_response = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        json={"outcome": FitOutcome.returned.value, "fit_notes": "Sleeves were too long."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["outcome"] == "returned"
    assert update_response.json()["fit_notes"] == "Sleeves were too long."

    list_response = client.get(f"/api/v1/purchases/user/{LOCAL_USER_ID}")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = client.delete(f"/api/v1/purchases/{purchase['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == purchase["id"]

    recall_after = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "sleeves long", "top_k": 3},
    )
    assert recall_after.status_code == 200
    assert recall_after.json()["facts"] == []
