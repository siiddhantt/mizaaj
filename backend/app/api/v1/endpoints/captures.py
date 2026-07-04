from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import (
    get_auth_context,
    get_extraction_gateway,
    get_memory_gateway,
    get_store,
)
from app.domain.captures.schemas import CaptureCreate, CaptureResponse, ConfirmCaptureRequest
from app.domain.captures.service import CaptureService
from app.domain.extraction.gateway import ExtractionGateway
from app.domain.memory.gateway import MemoryGateway
from app.storage.store import MizaajStore

router = APIRouter()


@router.get("/users/{user_id}", response_model=list[CaptureResponse])
async def list_captures(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> list[CaptureResponse]:
    user_id = assert_current_user(user_id, auth)
    return CaptureService(store).list_captures(user_id)


@router.get("/{capture_id}", response_model=CaptureResponse)
async def get_capture(
    capture_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> CaptureResponse:
    return CaptureService(store).get_capture(auth.user_id, capture_id)


@router.post("", response_model=CaptureResponse)
async def create_capture(
    payload: CaptureCreate,
    store: MizaajStore = Depends(get_store),
    extractor: ExtractionGateway = Depends(get_extraction_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> CaptureResponse:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await CaptureService(store, extractor).create_capture(payload)


@router.post("/{capture_id}/confirm", response_model=CaptureResponse)
async def confirm_capture(
    capture_id: UUID,
    payload: ConfirmCaptureRequest,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> CaptureResponse:
    capture = store.get_capture(capture_id)
    assert_current_user(capture.user_id, auth)
    return await CaptureService(store, memory_gateway=memory).confirm_capture(capture_id, payload)


@router.delete("/{capture_id}", response_model=CaptureResponse)
async def delete_capture(
    capture_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> CaptureResponse:
    return await CaptureService(store, memory_gateway=memory).delete_capture(
        auth.user_id, capture_id
    )
