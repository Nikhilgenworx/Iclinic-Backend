from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.data.clients.postgres_client import get_db

DBSession = Annotated[Session, Depends(get_db)]

# Optional bearer scheme — makes Swagger show the "Authorize" button
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Extract and validate the current user from:
    1. Authorization: Bearer <token> header (Swagger UI, cross-origin), OR
    2. access_token cookie (same-origin browser requests)
    """
    token = None

    # Try Authorization header first (from Swagger or backendClient)
    if credentials:
        token = credentials.credentials

    # Fallback to cookie
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    return payload


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Dependency factory to enforce role-based access."""

    def role_checker(current_user: CurrentUser) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
