"""FastAPI authentication dependency functions."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict | None:
    """
    Returns the decoded JWT payload if a valid Bearer token is provided,
    otherwise returns None.

    Use this on existing endpoints during gradual auth rollout — unauthenticated
    requests continue to work as before.
    """
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    return payload  # None if token is invalid


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Requires a valid Bearer token. Raises 401 if missing or invalid.

    Use this on endpoints that must be protected.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
