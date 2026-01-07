"""
D&D Combat Engine - Authentication Middleware
JWT token validation for protected endpoints.
"""
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.engine import get_session
from app.database.models import User
from app.services.auth_service import AuthService
from app.core.errors import AuthError, TokenInvalidError, ErrorCode

# HTTP Bearer token extractor
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """
    Authentication middleware for FastAPI.

    Provides dependency injection functions for:
    - Required authentication (raises error if not authenticated)
    - Optional authentication (returns None if not authenticated)
    """

    @staticmethod
    async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        """
        Get the current authenticated user.

        Use as a FastAPI dependency for protected endpoints.

        Raises:
            AuthError: If no token provided
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token has expired
        """
        if not credentials:
            raise AuthError(
                code=ErrorCode.AUTH_UNAUTHORIZED,
                message="Authentication required",
                recovery_hint="Please log in to continue"
            )

        auth_service = AuthService(session)
        return await auth_service.validate_access_token(credentials.credentials)

    @staticmethod
    async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        session: AsyncSession = Depends(get_session),
    ) -> Optional[User]:
        """
        Get the current user if authenticated, otherwise None.

        Use as a FastAPI dependency for endpoints that work with
        or without authentication.
        """
        if not credentials:
            return None

        try:
            auth_service = AuthService(session)
            return await auth_service.validate_access_token(credentials.credentials)
        except (AuthError, TokenInvalidError):
            return None


# Convenience dependency functions
get_current_user = AuthMiddleware.get_current_user
get_current_user_optional = AuthMiddleware.get_current_user_optional


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Dependency that requires authentication.

    Alias for get_current_user for semantic clarity.
    """
    return await AuthMiddleware.get_current_user(credentials, session)


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """
    Dependency that optionally authenticates.

    Alias for get_current_user_optional for semantic clarity.
    """
    return await AuthMiddleware.get_current_user_optional(credentials, session)


# WebSocket authentication helper
async def authenticate_websocket(token: str, session: AsyncSession) -> Optional[User]:
    """
    Authenticate a WebSocket connection using a token.

    WebSocket connections can't use HTTP headers the same way,
    so the token is passed as a query parameter or in the first message.

    Args:
        token: JWT access token
        session: Database session

    Returns:
        User if authenticated, None otherwise
    """
    if not token:
        return None

    try:
        auth_service = AuthService(session)
        return await auth_service.validate_access_token(token)
    except Exception:
        return None
