from fastapi import APIRouter

from app.api.v1.endpoints import (
    ask,
    auth,
    captures,
    memory,
    products,
    profiles,
    purchases,
    recommendations,
    system,
    uploads,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ask.router, prefix="/ask", tags=["ask"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(captures.router, prefix="/captures", tags=["captures"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["purchases"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
