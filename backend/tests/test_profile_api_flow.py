from fastapi.testclient import TestClient

from app.core.dependencies import get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubMemoryGateway


def test_profile_update_rebuilds_private_memory():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = TestClient(app)

    update_response = client.put(
        f"/api/v1/profiles/{LOCAL_USER_ID}",
        json={
            "display_name": "Sid",
            "body_notes": "Avoid boxy cropped jackets.",
            "sensitivities": ["scratchy wool"],
        },
    )
    assert update_response.status_code == 200

    recall_response = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "scratchy wool", "top_k": 3},
    )
    assert recall_response.status_code == 200
    assert recall_response.json()["facts"]

    second_update = client.put(
        f"/api/v1/profiles/{LOCAL_USER_ID}",
        json={"sensitivities": ["tight armholes"]},
    )
    assert second_update.status_code == 200

    old_recall = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "scratchy wool", "top_k": 3},
    )
    assert old_recall.status_code == 200
    assert old_recall.json()["facts"] == []

    new_recall = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "tight armholes", "top_k": 3},
    )
    assert new_recall.status_code == 200
    assert new_recall.json()["facts"]
