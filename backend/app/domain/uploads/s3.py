import boto3
from botocore.client import Config

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError, ProviderRequestError
from app.domain.uploads.gateway import UploadGateway
from app.domain.uploads.schemas import UploadIntentRequest, UploadIntentResponse, build_upload_path


class S3UploadGateway(UploadGateway):
    def __init__(self, settings: Settings):
        if not settings.s3_bucket:
            raise ProviderNotConfiguredError("S3_BUCKET is required for upload intents.")
        if bool(settings.s3_access_key_id) != bool(settings.s3_secret_access_key):
            raise ProviderNotConfiguredError(
                "Both S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required."
            )

        self.settings = settings
        client_options = {
            "service_name": "s3",
            "region_name": settings.s3_region,
            "config": Config(signature_version="s3v4"),
        }
        if settings.s3_endpoint_url:
            client_options["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            client_options["aws_access_key_id"] = settings.s3_access_key_id
            client_options["aws_secret_access_key"] = settings.s3_secret_access_key
        self.client = boto3.client(**client_options)

    async def create_intent(self, request: UploadIntentRequest) -> UploadIntentResponse:
        path = build_upload_path(request.user_id, request.file_name)
        try:
            upload_url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.settings.s3_bucket,
                    "Key": path,
                    "ContentType": request.content_type,
                },
                ExpiresIn=self.settings.s3_presign_expires_seconds,
                HttpMethod="PUT",
            )
        except Exception as exc:
            raise ProviderRequestError("Could not create S3 upload intent.") from exc

        return UploadIntentResponse(
            bucket=self.settings.s3_bucket,
            path=path,
            provider="s3",
            upload_url=upload_url,
            public_url=self._public_url(path),
            max_upload_mb=self.settings.max_upload_mb,
            metadata={"contentType": request.content_type},
        )

    def _public_url(self, path: str) -> str | None:
        if not self.settings.s3_public_base_url:
            return None
        return f"{self.settings.s3_public_base_url.rstrip('/')}/{path}"
