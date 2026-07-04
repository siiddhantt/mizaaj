from collections.abc import AsyncIterator
from urllib.parse import urlencode
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.schemas import (
    FitMemoryEntry,
    ForgetScope,
    MemoryContext,
    MemoryContextFact,
    RecallFitContextRequest,
)


class CogneeCloudMemoryGateway(MemoryGateway):
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not settings.cognee_cloud_base_url or not settings.cognee_cloud_api_key:
            raise ProviderNotConfiguredError("Cognee Cloud URL and API key are required")
        self.settings = settings
        self.transport = transport

    async def remember_private(self, user_id: UUID, entry: FitMemoryEntry) -> None:
        await self._request(
            "POST",
            "/api/v1/remember",
            content=_AsyncBytes(self._encoded_form(self._remember_form(user_id, entry))),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        payload = await self._request(
            "POST",
            "/api/v1/recall",
            json={
                "searchType": "GRAPH_COMPLETION",
                "query": query.query,
                "datasets": [self._dataset_name(query.user_id)],
                "topK": query.top_k,
                "includeReferences": True,
            },
        )
        raw_results = payload if isinstance(payload, list) else payload.get("results", [])
        return MemoryContext(
            user_id=query.user_id,
            query=query.query,
            facts=[
                MemoryContextFact(text=str(item), source="cognee_cloud")
                for item in raw_results[: query.top_k]
            ],
        )

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None:
        if scope != ForgetScope.all_private:
            raise NotImplementedError("Granular Cognee Cloud forgetting is not wired yet")
        await self._request(
            "POST",
            "/api/v1/forget",
            json={"dataset": self._dataset_name(user_id), "everything": False, "memoryOnly": False},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        content: httpx.AsyncByteStream | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict | list:
        request_headers = self._headers() | (headers or {})
        base_url = str(self.settings.cognee_cloud_base_url).rstrip("/")
        async with httpx.AsyncClient(
            base_url=base_url,
            headers=request_headers,
            timeout=self.settings.cognee_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.request(method, path, json=json, content=content)
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict[str, str]:
        api_key = self.settings.cognee_cloud_api_key or ""
        return {
            "Authorization": f"Bearer {api_key}",
            "X-Api-Key": api_key,
        }

    def _remember_form(self, user_id: UUID, entry: FitMemoryEntry) -> list[tuple[str, str]]:
        form = [
            ("data", entry.text),
            ("datasetName", self._dataset_name(user_id)),
            ("run_in_background", "false"),
            ("custom_prompt", self._memory_extraction_prompt()),
        ]
        form.extend(("node_set", tag) for tag in entry.tags)
        return form

    def _encoded_form(self, form: list[tuple[str, str]]) -> bytes:
        return urlencode(form).encode("utf-8")

    def _memory_extraction_prompt(self) -> str:
        return (
            "Extract private clothing fit memory for Mizaaj. Preserve brand, category, size system "
            "(UK, EU, US, alpha, numeric), silhouette, fabric feel, body fit, try-on outcome, "
            "and evidence source. Do not infer unsupported facts."
        )

    def _dataset_name(self, user_id: UUID) -> str:
        return f"{self.settings.cognee_dataset_prefix}_{user_id.hex}"


class _AsyncBytes(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.content
