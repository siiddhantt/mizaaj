from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import get_auth_context, get_memory_gateway, get_store
from app.domain.memory.gateway import MemoryGateway
from app.domain.profiles.schemas import FitProfile, FitProfileUpdate
from app.domain.profiles.service import ProfileService
from app.storage.store import MizaajStore

router = APIRouter()


@router.get("/{user_id}", response_model=FitProfile)
async def get_profile(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> FitProfile:
    user_id = assert_current_user(user_id, auth)
    return ProfileService(store).get_profile(user_id)


@router.put("/{user_id}", response_model=FitProfile)
async def update_profile(
    user_id: UUID,
    payload: FitProfileUpdate,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> FitProfile:
    user_id = assert_current_user(user_id, auth)
    return await ProfileService(store, memory).update_profile(user_id, payload)
