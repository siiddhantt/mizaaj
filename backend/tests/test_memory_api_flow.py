from fastapi.testclient import TestClient

from app.core.dependencies import get_memory_gateway, get_store
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import FailingRecallMemoryGateway


def test_recall_returns_degraded_context_when_memory_provider_fails():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    app.dependency_overrides[get_store] = lambda: InMemoryStore()
    app.dependency_overrides[get_memory_gateway] = lambda: FailingRecallMemoryGateway()
    client = TestClient(app)

    response = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "shoulder room", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(LOCAL_USER_ID),
        "query": "shoulder room",
        "facts": [],
        "status": "degraded",
        "error": "memory recall timed out",
    }
