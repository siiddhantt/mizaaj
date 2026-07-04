from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import get_auth_context, get_memory_gateway, get_store
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.schemas import ForgetScope, MemoryContext, RecallFitContextRequest
from app.domain.privacy.schemas import UserDataDeletionResult
from app.domain.privacy.service import PrivacyService
from app.storage.store import MizaajStore

router = APIRouter()


@router.post("/recall", response_model=MemoryContext)
async def recall_fit_context(
    payload: RecallFitContextRequest,
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryContext:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    try:
        return await memory.recall_private(payload)
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        return MemoryContext.degraded(payload.user_id, payload.query, error)


@router.delete("/users/{user_id}")
async def forget_user_memory(
    user_id: UUID,
    scope: ForgetScope = ForgetScope.all_private,
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, str]:
    user_id = assert_current_user(user_id, auth)
    await memory.forget_private(user_id, scope)
    return {"status": "forgotten", "scope": scope.value}


@router.delete("/users/{user_id}/app-data", response_model=UserDataDeletionResult)
async def delete_user_data(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> UserDataDeletionResult:
    user_id = assert_current_user(user_id, auth)
    return await PrivacyService(store, memory).delete_user_data(user_id)
