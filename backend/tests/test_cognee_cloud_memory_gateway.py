from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.domain.memory.cognee_cloud import CogneeCloudMemoryGateway
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
    form = parse_qs(body)
    assert request.method == "POST"
    assert request.url.path == "/api/v1/remember"
    assert request.headers["authorization"] == "Bearer test-cloud-key"
    assert request.headers["x-api-key"] == "test-cloud-key"
    assert "application/x-www-form-urlencoded" in request.headers["content-type"]
    assert form["datasetName"] == ["mizaaj_user_00000000000040008000000000000001"]
    assert form["node_set"] == ["source:purchase", "brand:uniqlo"]
    assert form["data"] == ["Uniqlo M shirt worked well at the shoulders."]


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
    assert request.headers["authorization"] == "Bearer test-cloud-key"
    assert request.headers["x-api-key"] == "test-cloud-key"
    assert request.read()
    assert b'"searchType":"GRAPH_COMPLETION"' in request.content
    assert b'"query":"What size should I buy?"' in request.content
    assert b'"topK":3' in request.content
    assert context.facts[0].source == "cognee_cloud"
    assert "Start with M" in context.facts[0].text


@pytest.mark.asyncio
async def test_cloud_forget_deletes_private_dataset():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    gateway = CogneeCloudMemoryGateway(cloud_settings(), httpx.MockTransport(handler))

    await gateway.forget_private(USER_ID, ForgetScope.all_private)

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/forget"
    assert b'"dataset":"mizaaj_user_00000000000040008000000000000001"' in request.content
    assert b'"everything":false' in request.content
    assert b'"memoryOnly":false' in request.content
