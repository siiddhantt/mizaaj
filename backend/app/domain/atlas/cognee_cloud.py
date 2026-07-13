import httpx

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError
from app.domain.atlas.gateway import AtlasGateway
from app.domain.atlas.schemas import AtlasContext, AtlasRecallRequest
from app.domain.memory.recall import recall_item_to_fact


class CogneeCloudAtlasGateway(AtlasGateway):
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not settings.cognee_cloud_base_url or not settings.cognee_cloud_api_key:
            raise ProviderNotConfiguredError("Cognee Cloud URL and API key are required")
        self.settings = settings
        self.transport = transport

    async def recall_public(self, request: AtlasRecallRequest) -> AtlasContext:
        payload = await self._request(
            "POST",
            "/api/v1/recall",
            json={
                "searchType": "GRAPH_COMPLETION",
                "query": request.query,
                "datasets": [self.settings.atlas_dataset_name],
                "topK": request.top_k,
                "includeReferences": True,
                "onlyContext": True,
                "systemPrompt": (
                    "Return only source-backed public clothing facts relevant to the exact brand, "
                    "product identifiers, category, and region in the query. Exclude unrelated "
                    "brands and products. Preserve source URLs, identifiers, size labels, and "
                    "measurements. When no exact SKU, URL, or product identifier matches, describe "
                    "results as separate same-brand references rather than facts about the queried "
                    "item. Never state a personal preference or outcome."
                ),
            },
        )
        raw_results = payload if isinstance(payload, list) else payload.get("results", [])
        return AtlasContext(
            query=request.query,
            facts=[
                recall_item_to_fact(item, "mizaaj_atlas") for item in raw_results[: request.top_k]
            ],
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> dict | list:
        base_url = str(self.settings.cognee_cloud_base_url).rstrip("/")
        async with httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": self.settings.cognee_cloud_api_key or ""},
            timeout=self.settings.cognee_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.request(method, path, json=json)
            response.raise_for_status()
            return response.json()
