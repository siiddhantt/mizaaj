from uuid import UUID

from fastapi.testclient import TestClient

from app.core.auth import local_auth_context
from app.core.dependencies import (
    get_atlas_gateway,
    get_auth_context,
    get_extraction_gateway,
    get_memory_gateway,
    get_store,
)
from app.domain.ask.schemas import SavedMemoryRecord
from app.domain.common import ClothingCategory
from app.domain.products.schemas import ProductSnapshot
from app.main import create_app
from app.storage.in_memory import LOCAL_USER_ID, InMemoryStore
from tests.stubs import StubAtlasGateway, StubExtractionGateway, StubMemoryGateway


def make_test_client(app):
    app.dependency_overrides[get_auth_context] = local_auth_context
    return TestClient(app)


def test_ask_api_returns_and_remembers_memory_drafts():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    app.dependency_overrides[get_atlas_gateway] = lambda: StubAtlasGateway()
    client = make_test_client(app)
    product = store.list_products()[0]

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "question": "What size should I buy?",
            "context_notes": "I prefer relaxed drape and sleeves that do not run long.",
        },
    )

    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"]
    assert payload["memory_drafts"]

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "drafts": payload["memory_drafts"],
            "question": payload["question"],
            "answer": payload["answer"],
            "product_id": str(product.id),
            "evidence": payload["evidence"],
            "recalled_facts": payload["recalled_facts"],
        },
    )

    assert remember_response.status_code == 200
    assert remember_response.json()["memory_status"] == "indexed"
    assert remember_response.json()["memory_record"]["question"] == payload["question"]

    saved_response = client.get(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}")
    assert saved_response.status_code == 200
    assert saved_response.json()[0]["remembered"]

    memory_id = saved_response.json()[0]["id"]
    delete_response = client.delete(f"/api/v1/ask/memories/{memory_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == memory_id

    saved_after_delete = client.get(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}")
    assert saved_after_delete.status_code == 200
    assert saved_after_delete.json() == []


def test_remembering_capture_backed_chat_promotes_product_identity():
    get_store.cache_clear()
    get_extraction_gateway.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["Zara linen shirt with UK L and relaxed shoulders."],
            "assets": [],
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "capture_id": capture["id"],
            "question": "What should I remember about this shirt?",
        },
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "drafts": payload["memory_drafts"],
            "question": payload["question"],
            "answer": payload["answer"],
            "capture_id": capture["id"],
        },
    )

    assert remember_response.status_code == 200
    memory_record = remember_response.json()["memory_record"]
    assert memory_record["product_id"]
    assert memory_record["capture_id"] == capture["id"]

    promoted_capture = client.get(f"/api/v1/captures/{capture['id']}").json()
    assert promoted_capture["confirmed"] is True
    assert promoted_capture["product_snapshot"]["id"] == memory_record["product_id"]

    products = client.get("/api/v1/products").json()
    assert memory_record["product_id"] in {product["id"] for product in products}


def test_product_list_backfills_legacy_capture_backed_memory_identity():
    get_store.cache_clear()
    get_extraction_gateway.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["The Bear House black tee with UK L and EUR L labels."],
            "assets": [],
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()
    legacy_record = store.save_memory_record(
        SavedMemoryRecord(
            user_id=LOCAL_USER_ID,
            question="What should I remember?",
            answer="Remember the visible size labels.",
            capture_id=capture["id"],
            memory_status="indexed",
        )
    )

    products = client.get("/api/v1/products").json()

    assert products
    promoted_product = next(
        product for product in products if product["source_capture_id"] == capture["id"]
    )
    assert promoted_product["source_capture_id"] == capture["id"]
    promoted_record = store.get_saved_memory(legacy_record.id)
    assert str(promoted_record.product_id) == promoted_product["id"]
    assert legacy_record.capture_id is not None
    promoted_capture = store.get_capture(legacy_record.capture_id)
    assert promoted_capture.confirmed is True
    assert str(promoted_capture.product_snapshot.id) == promoted_product["id"]


def test_product_list_does_not_promote_capture_linked_to_existing_product():
    get_store.cache_clear()
    get_extraction_gateway.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_extraction_gateway] = lambda: StubExtractionGateway()
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)
    existing_product = store.list_products()[0]

    capture_response = client.post(
        "/api/v1/captures",
        json={
            "user_id": str(LOCAL_USER_ID),
            "source_type": "manual",
            "text_blocks": ["More page screenshots for the same Bear House black tee."],
            "assets": [],
        },
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "capture_id": capture["id"],
            "question": "Remember that these details belong to my existing tee.",
        },
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "drafts": payload["memory_drafts"],
            "question": payload["question"],
            "answer": payload["answer"],
            "product_id": str(existing_product.id),
            "capture_id": capture["id"],
        },
    )
    assert remember_response.status_code == 200
    memory_record = remember_response.json()["memory_record"]
    assert memory_record["product_id"] == str(existing_product.id)
    assert memory_record["capture_id"] == capture["id"]

    products = client.get("/api/v1/products").json()
    assert str(existing_product.id) in {product["id"] for product in products}
    assert capture["id"] not in {
        product["source_capture_id"] for product in products if product["source_capture_id"]
    }

    linked_capture = store.get_capture(UUID(capture["id"]))
    assert linked_capture.confirmed is False
    assert linked_capture.product_snapshot is None
    assert linked_capture.linked_product_id == existing_product.id
    indexed = memory._entries[LOCAL_USER_ID]
    assert indexed
    assert all(
        not entry.subject.startswith("product:")
        or entry.subject.startswith(f"product:{existing_product.id}")
        for entry in indexed
    )
    assert all(
        not tag.startswith("product:") or tag == f"product:{existing_product.id}"
        for entry in indexed
        for tag in entry.tags
    )


def test_ask_outcome_note_creates_memory_drafts_instead_of_size_advice():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)
    product = store.list_products()[0]

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "question": (
                "I kept it. The fit is good overall and does not feel tight around "
                "my stomach or chest. I like the subtle artwork."
            ),
        },
    )

    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"].startswith("Got it.")
    assert "Start with" not in payload["answer"]
    assert {draft["kind"] for draft in payload["memory_drafts"]} >= {
        "fit_outcome",
        "fit_preference",
    }


def test_ask_uses_unique_size_candidates_for_calibration_size():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)
    product = store.save_product(
        ProductSnapshot(
            brand="The Bear House",
            title="Men relaxed T-shirt",
            category=ClothingCategory.tshirt,
            size_options=[
                "S",
                "M",
                "L",
                "XL",
                "XXL",
                "3XL",
                "Standard S",
                "Standard M",
                "Standard L",
                "Standard XL",
                "Standard XXL",
                "Standard 3XL",
            ],
        )
    )

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "question": "What size should I buy?",
        },
    )

    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert "start with l" in payload["answer"].lower()
    assert "start with 3xl" not in payload["answer"].lower()


def test_ask_memory_clear_removes_saved_rows_and_private_index():
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    app = create_app()
    store = InMemoryStore.seeded()
    memory = StubMemoryGateway()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_memory_gateway] = lambda: memory
    client = make_test_client(app)
    product = store.list_products()[0]

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "user_id": str(LOCAL_USER_ID),
            "product_id": str(product.id),
            "question": "What should I remember?",
            "context_notes": "Balloon cuffs are uncomfortable on me.",
        },
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()

    remember_response = client.post(
        "/api/v1/ask/remember",
        json={
            "user_id": str(LOCAL_USER_ID),
            "drafts": payload["memory_drafts"],
            "question": payload["question"],
            "answer": payload["answer"],
            "product_id": str(product.id),
        },
    )
    assert remember_response.status_code == 200

    recall_before = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "balloon cuffs uncomfortable", "top_k": 3},
    )
    assert recall_before.status_code == 200
    assert recall_before.json()["facts"]

    clear_response = client.delete(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}")
    assert clear_response.status_code == 200
    assert clear_response.json()["deleted"] == 1

    saved_after_clear = client.get(f"/api/v1/ask/memories/users/{LOCAL_USER_ID}")
    assert saved_after_clear.status_code == 200
    assert saved_after_clear.json() == []

    recall_after = client.post(
        "/api/v1/memory/recall",
        json={"user_id": str(LOCAL_USER_ID), "query": "balloon cuffs uncomfortable", "top_k": 3},
    )
    assert recall_after.status_code == 200
    assert recall_after.json()["facts"] == []
