import asyncio
import importlib
import os
from uuid import UUID

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


class CogneeLocalMemoryGateway(MemoryGateway):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def remember_private(self, user_id: UUID, entry: FitMemoryEntry) -> None:
        import cognee

        self._configure_cognee_environment()
        await asyncio.wait_for(
            cognee.remember(
                entry.text,
                dataset_name=self._dataset_name(user_id),
                node_set=entry.tags,
                self_improvement=self.settings.cognee_self_improvement,
                llm_config=self._llm_config(),
                embedding_config=self._embedding_config(),
            ),
            timeout=self.settings.cognee_timeout_seconds,
        )

    async def recall_private(self, query: RecallFitContextRequest) -> MemoryContext:
        import cognee

        self._configure_cognee_environment()
        results = await asyncio.wait_for(
            cognee.recall(
                query.query,
                datasets=[self._dataset_name(query.user_id)],
                top_k=query.top_k,
                llm_config=self._llm_config(),
                embedding_config=self._embedding_config(),
            ),
            timeout=self.settings.cognee_timeout_seconds,
        )
        return MemoryContext(
            user_id=query.user_id,
            query=query.query,
            facts=[recall_item_to_fact(item, "cognee") for item in results[: query.top_k]],
        )

    async def forget_private(self, user_id: UUID, scope: ForgetScope) -> None:
        import cognee

        if scope != ForgetScope.all_private:
            raise NotImplementedError("Granular local Cognee forgetting is not wired yet")
        await cognee.forget(dataset=self._dataset_name(user_id))

    def _dataset_name(self, user_id: UUID) -> str:
        return f"{self.settings.cognee_dataset_prefix}_{user_id.hex}"

    def _configure_cognee_environment(self) -> None:
        llm_config = self._llm_config()
        embedding_config = self._embedding_config()

        os.environ["LLM_PROVIDER"] = llm_config.llm_provider
        os.environ["LLM_MODEL"] = llm_config.llm_model
        os.environ["LLM_ENDPOINT"] = llm_config.llm_endpoint
        os.environ["LLM_API_KEY"] = llm_config.llm_api_key or ""
        os.environ["EMBEDDING_PROVIDER"] = embedding_config.embedding_provider or ""
        os.environ["EMBEDDING_MODEL"] = embedding_config.embedding_model or ""
        os.environ["EMBEDDING_DIMENSIONS"] = str(embedding_config.embedding_dimensions or "")
        if embedding_config.embedding_endpoint:
            os.environ["EMBEDDING_ENDPOINT"] = embedding_config.embedding_endpoint
        if embedding_config.embedding_api_key:
            os.environ["EMBEDDING_API_KEY"] = embedding_config.embedding_api_key

        self._clear_cognee_config_caches()

    def _clear_cognee_config_caches(self) -> None:
        from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
        from cognee.infrastructure.llm.config import get_llm_config

        get_llm_config.cache_clear()
        get_embedding_config.cache_clear()
        try:
            llm_client_module = importlib.import_module(
                "cognee.infrastructure.llm.structured_output_framework."
                "litellm_instructor.llm.get_llm_client"
            )

            llm_client_module._get_llm_client_cached.cache_clear()
        except Exception:
            return

    def _llm_config(self):
        from cognee.infrastructure.llm.config import LLMConfig

        api_key = self.settings.cognee_llm_api_key or self.settings.openrouter_api_key
        endpoint = self.settings.cognee_llm_endpoint or self.settings.openrouter_base_url
        model = self.settings.cognee_llm_model or self._openrouter_litellm_model()
        if not api_key:
            raise ProviderNotConfiguredError(
                "OPENROUTER_API_KEY or COGNEE_LLM_API_KEY is required for Cognee local memory."
            )

        return LLMConfig(
            llm_provider=self.settings.cognee_llm_provider,
            llm_model=model,
            llm_endpoint=endpoint,
            llm_api_key=api_key,
        )

    def _embedding_config(self):
        from cognee.infrastructure.databases.vector.embeddings.config import EmbeddingConfig

        return EmbeddingConfig(
            embedding_provider=self.settings.cognee_embedding_provider,
            embedding_model=self.settings.cognee_embedding_model,
            embedding_dimensions=self.settings.cognee_embedding_dimensions,
            embedding_endpoint=self.settings.cognee_embedding_endpoint,
            embedding_api_key=self.settings.cognee_embedding_api_key,
        )

    def _openrouter_litellm_model(self) -> str:
        model = self.settings.openrouter_text_model
        if self.settings.cognee_llm_provider == "custom" and not model.startswith("openrouter/"):
            return f"openrouter/{model}"
        return model
