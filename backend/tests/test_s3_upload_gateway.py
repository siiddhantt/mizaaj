from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError
from app.domain.uploads.s3 import S3UploadGateway
from app.domain.uploads.schemas import UploadIntentRequest


@pytest.mark.asyncio
async def test_s3_upload_gateway_creates_presigned_put_intent():
    gateway = S3UploadGateway(
        Settings(
            s3_endpoint_url="http://localhost:9000",
            s3_access_key_id="mizaaj",
            s3_secret_access_key="mizaaj-secret",
            s3_bucket="mizaaj-uploads",
            s3_public_base_url="http://localhost:9000/mizaaj-uploads",
        )
    )

    response = await gateway.create_intent(
        UploadIntentRequest(
            user_id=uuid4(),
            file_name="shirt tag.png",
            content_type="image/png",
        )
    )

    assert response.provider == "s3"
    assert response.upload_method == "PUT"
    assert response.upload_url.startswith("http://localhost:9000/mizaaj-uploads/")
    assert "shirt-tag.png" in response.path
    assert response.public_url == f"http://localhost:9000/mizaaj-uploads/{response.path}"


def test_s3_upload_gateway_requires_matching_static_keys():
    with pytest.raises(ProviderNotConfiguredError):
        S3UploadGateway(
            Settings(
                s3_access_key_id="mizaaj",
                s3_secret_access_key=None,
                s3_bucket="mizaaj-uploads",
            )
        )
