from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import (
    get_atlas_gateway,
    get_auth_context,
    get_memory_gateway,
    get_reasoning_gateway,
    get_store,
)
from app.domain.ask.schemas import (
    AskFitRequest,
    AskFitResponse,
    RememberMemoryDraftsRequest,
    RememberMemoryDraftsResponse,
    SavedMemoryRecord,
)
from app.domain.ask.service import AskFitService
from app.domain.atlas.gateway import AtlasGateway
from app.domain.memory.gateway import MemoryGateway
from app.domain.reasoning.gateway import ReasoningGateway
from app.storage.store import MizaajStore

router = APIRouter()


@router.post("", response_model=AskFitResponse)
async def ask_mizaaj(
    payload: AskFitRequest,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    atlas: AtlasGateway = Depends(get_atlas_gateway),
    reasoning: ReasoningGateway | None = Depends(get_reasoning_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> AskFitResponse:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await AskFitService(store, memory, atlas, reasoning).ask(payload)


@router.post("/remember", response_model=RememberMemoryDraftsResponse)
async def remember_ask_drafts(
    payload: RememberMemoryDraftsRequest,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> RememberMemoryDraftsResponse:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await AskFitService(store, memory).remember_drafts(payload)


@router.get("/memories/users/{user_id}", response_model=list[SavedMemoryRecord])
async def list_saved_ask_memories(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> list[SavedMemoryRecord]:
    user_id = assert_current_user(user_id, auth)
    return AskFitService(store, memory).list_saved_memories(user_id)


@router.delete("/memories/{memory_id}", response_model=SavedMemoryRecord)
async def delete_saved_ask_memory(
    memory_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> SavedMemoryRecord:
    return await AskFitService(store, memory).delete_saved_memory(auth.user_id, memory_id)


@router.delete("/memories/users/{user_id}")
async def delete_saved_ask_memories(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, int]:
    user_id = assert_current_user(user_id, auth)
    deleted = await AskFitService(store, memory).delete_all_saved_memories(user_id)
    return {"deleted": deleted}
