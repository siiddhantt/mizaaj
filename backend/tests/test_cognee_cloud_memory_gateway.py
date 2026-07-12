from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.domain.memory.cognee_cloud import CogneeCloudMemoryGateway
from app.domain.memory.recall import clean_recall_text
from app.domain.memory.schemas import FitMemoryEntry, ForgetScope, RecallFitContextRequest

USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def cloud_settings() -> Settings:
    return Settings(
        cognee_cloud_base_url="https://api.cognee.ai",
        cognee_cloud_api_key="test-cloud-key",
        cognee_dataset_prefix="mizaaj_user",
    )


@pytest.mark.asyncio
async def test_cloud_remember_uses_cognee_http_memory_api():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    await gateway.remember_private(
        USER_ID,
        FitMemoryEntry(
            subject="purchase:test",
            text="Uniqlo M shirt worked well at the shoulders.",
            tags=["source:purchase", "brand:uniqlo"],
        ),
    )

    request = requests[0]
    body = request.content.decode()
    assert request.method == "POST"
    assert request.url.path == "/api/v1/remember"
    assert request.headers["x-api-key"] == "test-cloud-key"
    assert "multipart/form-data" in request.headers["content-type"]
    assert 'name="datasetName"' in body
    assert "mizaaj_user_00000000000040008000000000000001" in body
    assert body.count('name="node_set"') == 2
    assert "source:purchase" in body
    assert "brand:uniqlo" in body
    assert 'name="data"; filename="purchase_test-' in body
    assert '.txt"' in body
    assert "Uniqlo M shirt worked well at the shoulders." in body


@pytest.mark.asyncio
async def test_cloud_recall_uses_graph_completion_with_private_dataset():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"answer": "Start with M.", "source": "graph"}])

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    context = await gateway.recall_private(
        RecallFitContextRequest(user_id=USER_ID, query="What size should I buy?", top_k=3)
    )

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/recall"
    assert request.headers["x-api-key"] == "test-cloud-key"
    assert request.read()
    assert b'"searchType":"GRAPH_COMPLETION"' in request.content
    assert b'"query":"What size should I buy?"' in request.content
    assert b'"topK":3' in request.content
    assert context.facts[0].source == "cognee_cloud"
    assert "Start with M" in context.facts[0].text


@pytest.mark.asyncio
async def test_cloud_recall_normalizes_reference_payloads():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "answer": (
                        "Relaxed black tees worked for chest comfort. Evidence: - chunk 1 of "
                        "document 2e58940a-ac5f-4629-898c-685c4d134203 "
                        "(data_id: 45fded56-845c-50b2-b078-0ff77ac2b61f, "
                        "chunk_id: 591dd396-7f8b-59bf-8743-43d621e333eb): "
                        '"User prefers relaxed drape."'
                    ),
                    "source": "graph",
                },
                (
                    "chunk 1 of document 877bf9b7-5a3e-46c4-bfd8-93a44469de4e "
                    "(data_id: c90bd137-8c71-5d68-abfa-99f10524b4f6): "
                    '"User prefers small tasteful artwork."'
                ),
            ],
        )

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    context = await gateway.recall_private(
        RecallFitContextRequest(user_id=USER_ID, query="What worked?", top_k=3)
    )

    assert context.facts[0].text == "Relaxed black tees worked for chest comfort."
    assert context.facts[1].text == "User prefers small tasteful artwork."
    assert "document" not in context.facts[0].text
    assert "data_id" not in context.facts[1].text


@pytest.mark.asyncio
async def test_cloud_forget_deletes_private_dataset():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET" and len(requests) == 1:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "name": "mizaaj_user_00000000000040008000000000000001",
                    }
                ],
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "22222222-2222-4222-8222-222222222222"}],
            )
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(500)

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    await gateway.forget_private(USER_ID, ForgetScope.all_private)

    assert [request.method for request in requests] == ["GET", "GET", "DELETE"]
    assert requests[2].url.path == (
        "/api/v1/datasets/11111111-1111-4111-8111-111111111111/"
        "data/22222222-2222-4222-8222-222222222222"
    )


@pytest.mark.asyncio
async def test_cloud_forget_falls_back_when_item_deletion_is_unavailable():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/datasets/":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "name": "mizaaj_user_00000000000040008000000000000001",
                    }
                ],
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "22222222-2222-4222-8222-222222222222"}],
            )
        if request.method == "DELETE":
            return httpx.Response(500)
        return httpx.Response(200, json={"status": "ok"})

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    await gateway.forget_private(USER_ID, ForgetScope.all_private)

    assert requests[-1].method == "POST"
    assert requests[-1].url.path == "/api/v1/forget"
    assert b'"dataset":"mizaaj_user_00000000000040008000000000000001"' in requests[-1].content
    assert b'"data_id":"22222222-2222-4222-8222-222222222222"' in requests[-1].content


def test_clean_recall_text_extracts_cognee_node_content():
    raw = (
        "Nodes: Node: memory __node_content_start__ Size L was kept and did not cling. "
        "__node_content_end__ Node: metadata"
    )

    assert clean_recall_text(raw) == "Size L was kept and did not cling."
