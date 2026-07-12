import re
from uuid import UUID, uuid4

import httpx

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.recall import recall_item_to_fact
from app.domain.memory.schemas import (
    FitMemoryEntry,
    ForgetScope,
    MemoryContext,
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
        source = re.sub(r"[^A-Za-z0-9._-]+", "_", entry.source_id or entry.subject).strip("._-")
        filename = f"{source}-{uuid4().hex}.txt"
        content, content_type = self._remember_multipart_body(user_id, entry, filename)
        await self._request(
            "POST",
            "/api/v1/remember",
            content=content,
            headers={"Content-Type": content_type},
        )

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        request_payload = {
            "searchType": "GRAPH_COMPLETION",
            "query": query.query,
            "datasets": [self._dataset_name(query.user_id)],
            "topK": query.top_k,
            "includeReferences": True,
            "onlyContext": True,
            "systemPrompt": (
                "Return only concise, directly relevant private clothing facts. Preserve product "
                "identity, size system, outcome, body-area fit, fabric feel, and whether the fact "
                "was observed or preferred. Do not invent or generalize beyond memory."
            ),
        }
        if query.session_id:
            request_payload["sessionId"] = query.session_id
        payload = await self._request(
            "POST",
            "/api/v1/recall",
            json=request_payload,
        )
        raw_results = payload if isinstance(payload, list) else payload.get("results", [])
        return MemoryContext(
            user_id=query.user_id,
            query=query.query,
            facts=[
                recall_item_to_fact(item, "cognee_cloud") for item in raw_results[: query.top_k]
            ],
        )

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None:
        if scope != ForgetScope.all_private:
            raise NotImplementedError("Granular Cognee Cloud forgetting is not wired yet")
        dataset_name = self._dataset_name(user_id)
        dataset_id = await self._dataset_id(dataset_name)
        if dataset_id is None:
            return
        payload = await self._request("GET", f"/api/v1/datasets/{dataset_id}/data")
        data_items = payload if isinstance(payload, list) else payload.get("data", [])
        for item in data_items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            data_id = str(item["id"])
            try:
                await self._request(
                    "DELETE",
                    f"/api/v1/datasets/{dataset_id}/data/{data_id}",
                )
            except httpx.HTTPStatusError:
                await self._request(
                    "POST",
                    "/api/v1/forget",
                    json={"dataset": dataset_name, "data_id": data_id},
                )

    async def _dataset_id(self, dataset_name: str) -> str | None:
        payload = await self._request("GET", "/api/v1/datasets/")
        datasets = payload if isinstance(payload, list) else payload.get("datasets", [])
        for dataset in datasets:
            if isinstance(dataset, dict) and dataset.get("name") == dataset_name:
                value = dataset.get("id")
                return str(value) if value else None
        return None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict | list:
        base_url = str(self.settings.cognee_cloud_base_url).rstrip("/")
        async with httpx.AsyncClient(
            base_url=base_url,
            headers=self._headers() | (headers or {}),
            timeout=self.settings.cognee_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.request(method, path, json=json, content=content)
            response.raise_for_status()
            return response.json() if response.content else {}

    def _headers(self) -> dict[str, str]:
        api_key = self.settings.cognee_cloud_api_key or ""
        return {
            "X-Api-Key": api_key,
        }

    def _remember_form(self, user_id: UUID, entry: FitMemoryEntry) -> list[tuple[str, str]]:
        form = [
            ("datasetName", self._dataset_name(user_id)),
            ("run_in_background", "false"),
            ("custom_prompt", self._memory_extraction_prompt()),
        ]
        form.extend(("node_set", tag) for tag in entry.tags)
        return form

    def _remember_multipart_body(
        self,
        user_id: UUID,
        entry: FitMemoryEntry,
        filename: str,
    ) -> tuple[bytes, str]:
        boundary = f"mizaaj-{uuid4().hex}"
        chunks: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    value.encode(),
                    b"\r\n",
                ]
            )

        def add_file(name: str, file_name: str, value: str) -> None:
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    (
                        f'Content-Disposition: form-data; name="{name}"; filename="{file_name}"\r\n'
                    ).encode(),
                    b"Content-Type: text/plain\r\n\r\n",
                    value.encode(),
                    b"\r\n",
                ]
            )

        for key, value in self._remember_form(user_id, entry):
            add_field(key, value)
        add_file("data", filename, entry.text)
        chunks.append(f"--{boundary}--\r\n".encode())
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def _memory_extraction_prompt(self) -> str:
        return (
            "Extract private clothing fit memory for Mizaaj. Preserve brand, category, size system "
            "(UK, EU, US, alpha, numeric), silhouette, fabric feel, body fit, try-on outcome, "
            "and evidence source. Do not infer unsupported facts."
        )

    def _dataset_name(self, user_id: UUID) -> str:
        return f"{self.settings.cognee_dataset_prefix}_{user_id.hex}"
