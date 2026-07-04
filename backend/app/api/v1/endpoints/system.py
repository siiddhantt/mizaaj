from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl

from app.core.config import Settings
from app.core.dependencies import get_app_settings

router = APIRouter()


class CloudUsageInfo(BaseModel):
    live_usage_available: bool
    billing_url: HttpUrl
    token_price_usd_per_million: float
    note: str


class SystemStatusResponse(BaseModel):
    app_name: str
    environment: str
    store_provider: str
    memory_provider: Literal["cognee_local", "cognee_cloud"]
    upload_provider: str
    extraction_provider: str
    cognee_dataset_prefix: str
    cognee_cloud_configured: bool
    cognee_timeout_seconds: float
    cloud_usage: CloudUsageInfo | None


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(
    settings: Settings = Depends(get_app_settings),
) -> SystemStatusResponse:
    return SystemStatusResponse(
        app_name=settings.app_name,
        environment=settings.environment,
        store_provider=settings.store_provider,
        memory_provider=settings.memory_provider,
        upload_provider=settings.upload_provider,
        extraction_provider=settings.extraction_provider,
        cognee_dataset_prefix=settings.cognee_dataset_prefix,
        cognee_cloud_configured=bool(
            settings.cognee_cloud_base_url and settings.cognee_cloud_api_key
        ),
        cognee_timeout_seconds=settings.cognee_timeout_seconds,
        cloud_usage=CloudUsageInfo(
            live_usage_available=False,
            billing_url="https://platform.cognee.ai/billing",
            token_price_usd_per_million=2.5,
            note="Cognee Cloud exposes balance and workspace usage in the billing dashboard.",
        )
        if settings.memory_provider == "cognee_cloud"
        else None,
    )
