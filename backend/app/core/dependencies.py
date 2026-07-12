from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from app.core.auth import AuthContext, authenticate_request
from app.core.config import Settings, get_settings
from app.domain.atlas.factory import create_atlas_gateway
from app.domain.atlas.gateway import AtlasGateway
from app.domain.extraction.factory import create_extraction_gateway
from app.domain.extraction.gateway import ExtractionGateway
from app.domain.memory.factory import create_memory_gateway
from app.domain.memory.gateway import MemoryGateway
from app.domain.reasoning.factory import create_reasoning_gateway
from app.domain.reasoning.gateway import ReasoningGateway
from app.domain.uploads.factory import create_upload_gateway
from app.domain.uploads.gateway import UploadGateway
from app.storage.factory import create_store
from app.storage.store import MizaajStore


@lru_cache
def get_store() -> MizaajStore:
    return create_store(get_settings())


@lru_cache
def get_memory_gateway() -> MemoryGateway:
    return create_memory_gateway(get_settings())


@lru_cache
def get_atlas_gateway() -> AtlasGateway:
    return create_atlas_gateway(get_settings())


@lru_cache
def get_extraction_gateway() -> ExtractionGateway:
    return create_extraction_gateway(get_settings())


@lru_cache
def get_reasoning_gateway() -> ReasoningGateway | None:
    return create_reasoning_gateway(get_settings())


@lru_cache
def get_upload_gateway() -> UploadGateway:
    return create_upload_gateway(get_settings())


def get_app_settings() -> Settings:
    return get_settings()


async def get_auth_context(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthContext:
    return await authenticate_request(request, settings)
