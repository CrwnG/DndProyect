"""
D&D Combat Engine - Authentication Service
JWT-based authentication with refresh tokens.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database.models import User, UserCreate, TokenPair
from app.core.errors import (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    AuthError,
    ValidationError,
    ErrorCode,
)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "dev-refresh-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 1 week


class AuthService:
    """
    Authentication service for user management and JWT tokens.

    Provides:
    - User registration with password hashing
    - Login with JWT token generation
    - Token refresh for extended sessions
    - Token validation for protected endpoints
    - Password reset (basic implementation)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # PASSWORD HASHING
    # =========================================================================

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by their ID."""
        statement = select(User).where(User.id == user_id, User.is_active == True)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by their username."""
        statement = select(User).where(User.username == username, User.is_active == True)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by their email."""
        statement = select(User).where(User.email == email, User.is_active == True)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def register(self, user_data: UserCreate) -> User:
        """
        Register a new user.

        Raises:
            ValidationError: If username or email already exists
        """
        # Check if username exists
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise ValidationError("username", "Username already taken")

        # Check if email exists
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            raise ValidationError("email", "Email already registered")

        # Create user with hashed password
        user = User(
            username=user_data.username,
            email=user_data.email.lower(),
            password_hash=self.hash_password(user_data.password),
            display_name=user_data.display_name or user_data.username,
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def login(self, username: str, password: str) -> Tuple[User, TokenPair]:
        """
        Authenticate a user and return tokens.

        Raises:
            InvalidCredentialsError: If credentials are invalid
        """
        # Try to find user by username or email
        user = await self.get_user_by_username(username)
        if not user:
            user = await self.get_user_by_email(username.lower())

        if not user:
            raise InvalidCredentialsError()

        if not self.verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        # Update last login
        user.last_login = datetime.utcnow()
        await self.session.commit()

        # Generate tokens
        tokens = self.create_tokens(user)

        return user, tokens

    async def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user's password.

        Returns:
            True if password was changed successfully
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        if not self.verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect")

        user.password_hash = self.hash_password(new_password)
        user.token_version += 1  # Invalidate all existing tokens
        user.updated_at = datetime.utcnow()
        await self.session.commit()

        return True

    async def logout(self, user_id: str) -> bool:
        """
        Logout user by incrementing token version.

        This invalidates all existing tokens for the user.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.token_version += 1
        await self.session.commit()

        return True

    # =========================================================================
    # JWT TOKEN MANAGEMENT
    # =========================================================================

    def create_tokens(self, user: User) -> TokenPair:
        """Create access and refresh tokens for a user."""
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def create_access_token(self, user: User) -> str:
        """Create an access token."""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user.id,
            "username": user.username,
            "type": "access",
            "version": user.token_version,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        """Create a refresh token."""
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": user.id,
            "type": "refresh",
            "version": user.token_version,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

    async def validate_access_token(self, token: str) -> User:
        """
        Validate an access token and return the user.

        Raises:
            TokenInvalidError: If token is malformed
            TokenExpiredError: If token has expired
            AuthError: If user not found or token version mismatch
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError:
            raise TokenInvalidError()

        if payload.get("type") != "access":
            raise TokenInvalidError()

        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError()

        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthError(
                code=ErrorCode.AUTH_UNAUTHORIZED,
                message="User not found"
            )

        # Check token version (for logout/password change)
        if payload.get("version") != user.token_version:
            raise TokenExpiredError()

        return user

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        Refresh tokens using a refresh token.

        Raises:
            TokenInvalidError: If refresh token is invalid
            TokenExpiredError: If refresh token has expired
        """
        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError:
            raise TokenInvalidError()

        if payload.get("type") != "refresh":
            raise TokenInvalidError()

        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError()

        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthError(
                code=ErrorCode.AUTH_UNAUTHORIZED,
                message="User not found"
            )

        # Check token version
        if payload.get("version") != user.token_version:
            raise TokenExpiredError()

        # Create new tokens
        return self.create_tokens(user)


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def get_auth_service(session: AsyncSession) -> AuthService:
    """Factory function for AuthService."""
    return AuthService(session)
