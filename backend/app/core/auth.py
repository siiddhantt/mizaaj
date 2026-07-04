from dataclasses import dataclass
from uuid import UUID, uuid5

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.core.config import Settings

LOCAL_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
CLERK_USER_NAMESPACE = UUID("8f3bcf84-d09c-4a4d-93c0-bdf5f7f52c19")


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    subject: str
    provider: str


_jwks_clients: dict[str, PyJWKClient] = {}


def auth_enabled(settings: Settings) -> bool:
    return settings.auth_required


def local_auth_context() -> AuthContext:
    return AuthContext(user_id=LOCAL_USER_ID, subject="local-dev", provider="local")


async def authenticate_request(request: Request, settings: Settings) -> AuthContext:
    if not auth_enabled(settings):
        return local_auth_context()

    token = _bearer_token(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if not settings.clerk_jwks_url or not settings.clerk_issuer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk authentication is enabled but not configured.",
        )

    try:
        payload = _decode_clerk_token(token, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing a user subject.",
        )

    return AuthContext(
        user_id=uuid5(CLERK_USER_NAMESPACE, subject),
        subject=subject,
        provider="clerk",
    )


def assert_current_user(requested_user_id: UUID, auth: AuthContext) -> UUID:
    if requested_user_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This resource belongs to a different user.",
        )
    return auth.user_id


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _decode_clerk_token(token: str, settings: Settings) -> dict[str, object]:
    jwks_client = _jwks_client(settings.clerk_jwks_url or "")
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    decode_options: dict[str, object] = {
        "algorithms": ["RS256"],
        "issuer": settings.clerk_issuer,
    }
    if settings.clerk_audience:
        decode_options["audience"] = settings.clerk_audience
    else:
        decode_options["options"] = {"verify_aud": False}

    return jwt.decode(token, signing_key.key, **decode_options)


def _jwks_client(jwks_url: str) -> PyJWKClient:
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(jwks_url)
    return _jwks_clients[jwks_url]
