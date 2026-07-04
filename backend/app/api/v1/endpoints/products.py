from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext
from app.core.dependencies import get_auth_context, get_memory_gateway, get_store
from app.core.errors import ForbiddenError
from app.domain.memory.gateway import MemoryGateway
from app.domain.memory.rebuilder import PrivateMemoryRebuilder
from app.domain.products.schemas import ProductSnapshot
from app.domain.products.service import ProductService
from app.storage.store import MizaajStore

router = APIRouter()


@router.get("", response_model=list[ProductSnapshot])
async def list_products(
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ProductSnapshot]:
    service = ProductService(store)
    service.backfill_saved_memory_products(auth.user_id)
    return [
        product for product in service.list_products() if _can_read_product(product, store, auth)
    ]


@router.get("/{product_id}", response_model=ProductSnapshot)
async def get_product(
    product_id: UUID,
    store: MizaajStore = Depends(get_store),
    auth: AuthContext = Depends(get_auth_context),
) -> ProductSnapshot:
    product = ProductService(store).get_product(product_id)
    if not _can_read_product(product, store, auth):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This product belongs to a different user.",
        )
    return product


@router.delete("/{product_id}", response_model=ProductSnapshot)
async def delete_product(
    product_id: UUID,
    store: MizaajStore = Depends(get_store),
    memory: MemoryGateway = Depends(get_memory_gateway),
    auth: AuthContext = Depends(get_auth_context),
) -> ProductSnapshot:
    product = ProductService(store).get_product(product_id)
    if not _can_read_product(product, store, auth):
        raise ForbiddenError("This product belongs to a different user.")
    if any(purchase.product_id == product_id for purchase in store.list_purchases(auth.user_id)):
        raise ForbiddenError("Cannot delete a product with saved outcomes.")

    deleted = store.delete_product(product_id)
    if product.source_capture_id is not None:
        capture = store.get_capture(product.source_capture_id)
        store.save_capture(
            capture.model_copy(
                update={
                    "product_snapshot": None,
                    "confirmed": False,
                    "memory_status": "not_indexed",
                    "memory_error": None,
                }
            )
        )
        await PrivateMemoryRebuilder(store, memory).rebuild_user(auth.user_id)
    return deleted


def _can_read_product(
    product: ProductSnapshot,
    store: MizaajStore,
    auth: AuthContext,
) -> bool:
    if product.source_capture_id is None:
        return auth.provider == "local"

    try:
        capture = store.get_capture(product.source_capture_id)
    except Exception:
        return False
    return capture.user_id == auth.user_id
