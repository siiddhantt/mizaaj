from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import get_auth_context, get_upload_gateway
from app.domain.uploads.gateway import UploadGateway
from app.domain.uploads.schemas import UploadIntentRequest, UploadIntentResponse

router = APIRouter()


@router.post("/intent", response_model=UploadIntentResponse)
async def create_upload_intent(
    payload: UploadIntentRequest,
    uploads: UploadGateway = Depends(get_upload_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> UploadIntentResponse:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await uploads.create_intent(payload)
