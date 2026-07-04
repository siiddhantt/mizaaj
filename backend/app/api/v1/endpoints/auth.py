from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import AuthContext
from app.core.dependencies import get_auth_context

router = APIRouter()


class CurrentUserResponse(BaseModel):
    user_id: UUID
    subject: str
    provider: str


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=auth.user_id,
        subject=auth.subject,
        provider=auth.provider,
    )
