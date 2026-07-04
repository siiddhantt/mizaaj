from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UploadIntentRequest(BaseModel):
    user_id: UUID
    file_name: str
    content_type: str


class UploadIntentResponse(BaseModel):
    bucket: str
    path: str
    provider: str
    upload_url: str
    upload_method: str = "PUT"
    public_url: str | None = None
    max_upload_mb: int
    metadata: dict[str, str] = Field(default_factory=dict)


def build_upload_path(user_id: UUID, file_name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ".-_" else "-" for char in file_name)
    return f"users/{user_id}/captures/{uuid4()}-{cleaned}"
