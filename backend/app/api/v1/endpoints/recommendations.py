from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import get_auth_context, get_memory_gateway, get_store
from app.domain.memory.gateway import MemoryGateway
from app.domain.recommendations.schemas import RecommendationRequest, RecommendationResponse
from app.domain.recommendations.service import RecommendationService
from app.storage.store import MizaajStore

router = APIRouter()


@router.post("", response_model=RecommendationResponse)
async def recommend_size(
    payload: RecommendationRequest,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> RecommendationResponse:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await RecommendationService(store, memory).recommend(payload)
