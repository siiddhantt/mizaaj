from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mizaaj API"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ]
    )

    database_url: str = "postgresql+psycopg://mizaaj:mizaaj@localhost:5432/mizaaj"
    store_provider: Literal["postgres", "memory"] = "postgres"

    memory_provider: Literal["cognee_local", "cognee_cloud"] = "cognee_local"
    cognee_dataset_prefix: str = "mizaaj_user"
    cognee_cloud_base_url: HttpUrl | None = None
    cognee_cloud_api_key: str | None = None
    cognee_llm_provider: str = "custom"
    cognee_llm_model: str | None = None
    cognee_llm_endpoint: str | None = None
    cognee_llm_api_key: str | None = None
    cognee_embedding_provider: str = "fastembed"
    cognee_embedding_model: str = "BAAI/bge-small-en-v1.5"
    cognee_embedding_dimensions: int = 384
    cognee_embedding_endpoint: str | None = None
    cognee_embedding_api_key: str | None = None
    cognee_self_improvement: bool = False
    cognee_timeout_seconds: float = 90

    extraction_provider: Literal["openrouter"] = "openrouter"
    extraction_max_images: int = 4
    extraction_max_text_chars: int = 12_000
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "deepseek/deepseek-v4-flash"
    openrouter_vision_model: str = "qwen/qwen3.7-plus"
    openrouter_site_url: str | None = "http://localhost:5173"
    openrouter_app_title: str = "Mizaaj"
    openrouter_timeout_seconds: float = 45
    openrouter_require_parameters: bool = True

    upload_provider: Literal["s3"] = "s3"
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = "mizaaj"
    s3_secret_access_key: str | None = "mizaaj-secret"
    s3_bucket: str = "mizaaj-uploads"
    s3_public_base_url: str | None = "http://localhost:9000/mizaaj-uploads"
    s3_presign_expires_seconds: int = 900
    max_upload_mb: int = 10

    auth_required: bool = False
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_audience: str | None = None

    @field_validator(
        "cognee_cloud_base_url",
        "cognee_cloud_api_key",
        "cognee_llm_model",
        "cognee_llm_endpoint",
        "cognee_llm_api_key",
        "cognee_embedding_endpoint",
        "cognee_embedding_api_key",
        "openrouter_api_key",
        "openrouter_site_url",
        "s3_endpoint_url",
        "s3_access_key_id",
        "s3_secret_access_key",
        "s3_public_base_url",
        "clerk_issuer",
        "clerk_jwks_url",
        "clerk_audience",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: object) -> object:
        return None if value == "" else value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
