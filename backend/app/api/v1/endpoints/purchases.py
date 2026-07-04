from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, assert_current_user
from app.core.dependencies import get_auth_context, get_memory_gateway, get_store
from app.domain.memory.gateway import MemoryGateway
from app.domain.purchases.schemas import PurchaseCreate, PurchaseRecord, PurchaseUpdate
from app.domain.purchases.service import PurchaseService
from app.storage.store import MizaajStore

router = APIRouter()


@router.get("/user/{user_id}", response_model=list[PurchaseRecord])
async def list_purchases(
    user_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> list[PurchaseRecord]:
    user_id = assert_current_user(user_id, auth)
    return PurchaseService(store).list_purchases(user_id)


@router.get("/{purchase_id}", response_model=PurchaseRecord)
async def get_purchase(
    purchase_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseRecord:
    return PurchaseService(store).get_purchase(auth.user_id, purchase_id)


@router.post("", response_model=PurchaseRecord)
async def create_purchase(
    payload: PurchaseCreate,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseRecord:
    payload = payload.model_copy(update={"user_id": assert_current_user(payload.user_id, auth)})
    return await PurchaseService(store, memory).create_purchase(payload)


@router.patch("/{purchase_id}", response_model=PurchaseRecord)
async def update_purchase(
    purchase_id: UUID,
    payload: PurchaseUpdate,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseRecord:
    return await PurchaseService(store, memory).update_purchase(auth.user_id, purchase_id, payload)


@router.delete("/{purchase_id}", response_model=PurchaseRecord)
async def delete_purchase(
    purchase_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseRecord:
    return await PurchaseService(store, memory).delete_purchase(auth.user_id, purchase_id)
