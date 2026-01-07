"""
D&D Combat Engine - Authentication Routes
User registration, login, and token management.
"""
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.engine import get_session
from app.database.models import User, UserCreate, UserLogin, UserUpdate, TokenPair, TokenRefresh
from app.services.auth_service import AuthService
from app.middleware.auth import get_current_user

router = APIRouter()


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class UserResponse(BaseModel):
    """User data response (excludes sensitive fields)."""
    id: str
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool
    created_at: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat(),
        )


class AuthResponse(BaseModel):
    """Authentication response with user and tokens."""
    user: UserResponse
    tokens: TokenPair


class MessageResponse(BaseModel):
    """Simple message response."""
    success: bool
    message: str


class PasswordChange(BaseModel):
    """Password change request."""
    old_password: str
    new_password: str


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new user account.

    Creates a new user with the provided credentials and returns
    authentication tokens for immediate login.
    """
    auth_service = AuthService(session)

    # Register user
    user = await auth_service.register(user_data)

    # Generate tokens
    tokens = auth_service.create_tokens(user)

    return AuthResponse(
        user=UserResponse.from_user(user),
        tokens=tokens,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    """
    Login with username/email and password.

    Returns authentication tokens on success.
    """
    auth_service = AuthService(session)

    user, tokens = await auth_service.login(credentials.username, credentials.password)

    return AuthResponse(
        user=UserResponse.from_user(user),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_data: TokenRefresh,
    session: AsyncSession = Depends(get_session),
):
    """
    Refresh access token using a refresh token.

    Use this endpoint when the access token expires to get
    a new token pair without requiring the user to log in again.
    """
    auth_service = AuthService(session)

    tokens = await auth_service.refresh_tokens(refresh_data.refresh_token)

    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Logout the current user.

    Invalidates all existing tokens for the user.
    """
    auth_service = AuthService(session)

    await auth_service.logout(current_user.id)

    return MessageResponse(
        success=True,
        message="Logged out successfully",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's profile.

    Requires authentication.
    """
    return UserResponse.from_user(current_user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update the current user's profile.

    Only updates provided fields.
    """
    auth_service = AuthService(session)

    updated_user = await auth_service.update_user(
        current_user.id,
        display_name=profile_data.display_name,
        avatar_url=profile_data.avatar_url,
    )

    return UserResponse.from_user(updated_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Change the current user's password.

    Requires the current password for verification.
    Invalidates all existing tokens after password change.
    """
    auth_service = AuthService(session)

    await auth_service.change_password(
        current_user.id,
        password_data.old_password,
        password_data.new_password,
    )

    return MessageResponse(
        success=True,
        message="Password changed successfully. Please log in again.",
    )


@router.get("/verify")
async def verify_token(
    current_user: User = Depends(get_current_user),
):
    """
    Verify the current access token is valid.

    Returns user info if token is valid.
    Useful for checking auth status on app startup.
    """
    return {
        "valid": True,
        "user": UserResponse.from_user(current_user),
    }
