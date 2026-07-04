from app.core.config import Settings
from app.domain.uploads.gateway import UploadGateway
from app.domain.uploads.s3 import S3UploadGateway


def create_upload_gateway(settings: Settings) -> UploadGateway:
    if settings.upload_provider == "s3":
        return S3UploadGateway(settings)
    raise ValueError(f"Unsupported upload provider: {settings.upload_provider}")
