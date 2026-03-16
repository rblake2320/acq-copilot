"""Authentication router: register, login, and current-user endpoints."""
from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.database import User
from app.services.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.auth_deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Payload for new-user registration."""

    username: str = Field(..., min_length=3, max_length=50, description="Chosen display name")
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")


class TokenResponse(BaseModel):
    """Standard OAuth2 token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Current-user info returned from /me."""

    id: str
    email: str
    role: str
    is_active: bool


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _user_to_token(user: User) -> str:
    """Mint an access token for the given User ORM object."""
    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/token", response_model=TokenResponse, summary="Login — get access token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Standard OAuth2 password flow.

    Accepts ``username`` (treated as email) and ``password`` as form data.
    Returns a Bearer token on success.
    """
    # Accept email in the username field (OAuth2 form convention)
    email_or_name = form_data.username.strip().lower()

    result = await db.execute(select(User).where(User.email == email_or_name))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("auth_login_failed", attempted_email=email_or_name)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = _user_to_token(user)
    logger.info("auth_login_success", user_id=str(user.id))
    return TokenResponse(access_token=token)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new user account and return an access token immediately.

    - ``username``: display name (stored in role field label — email is the unique key)
    - ``email``: must be unique across accounts
    - ``password``: min 8 characters, bcrypt-hashed before storage
    """
    # Check for existing account
    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    user = User(
        email=body.email.lower(),
        hashed_password=get_password_hash(body.password),
        role="analyst",  # default role for new registrations
        is_active=True,
    )
    db.add(user)
    await db.flush()  # get the auto-generated id before commit

    token = _user_to_token(user)
    logger.info("auth_register_success", user_id=str(user.id), email=user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Return profile information for the authenticated user.

    Requires a valid Bearer token in the ``Authorization`` header.
    """
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )
