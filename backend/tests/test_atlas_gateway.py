import httpx
import pytest

from app.core.config import Settings
from app.domain.atlas.cognee_cloud import CogneeCloudAtlasGateway
from app.domain.atlas.schemas import AtlasRecallRequest
from app.domain.atlas.seed import SeedAtlasGateway


@pytest.mark.asyncio
async def test_seed_atlas_recalls_source_labeled_public_facts():
    gateway = SeedAtlasGateway()

    context = await gateway.recall_public(
        AtlasRecallRequest(query="H&M oversized cotton black tshirt dropped shoulders", top_k=3)
    )

    assert context.status == "ready"
    assert context.facts
    assert context.facts[0].source.startswith("mizaaj_atlas:")
    assert "Public Atlas evidence" in context.facts[0].text
    assert "private" not in context.facts[0].source


@pytest.mark.asyncio
async def test_cloud_atlas_recall_uses_public_atlas_dataset():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[{"answer": "Public product evidence says this is oversized cotton."}],
        )

    gateway = CogneeCloudAtlasGateway(
        Settings(
            cognee_cloud_base_url="https://api.cognee.ai",
            cognee_cloud_api_key="test-key",
            atlas_dataset_name="mizaaj_atlas_seed_v2",
        ),
        httpx.MockTransport(handler),
    )

    context = await gateway.recall_public(AtlasRecallRequest(query="oversized cotton tee", top_k=2))

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/recall"
    assert request.headers["x-api-key"] == "test-key"
    assert b'"datasets":["mizaaj_atlas_seed_v2"]' in request.content
    assert b'"searchType":"GRAPH_COMPLETION"' in request.content
    assert context.facts[0].source == "mizaaj_atlas"
    assert "oversized cotton" in context.facts[0].text
