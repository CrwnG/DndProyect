"""
Unit tests for Authentication Service
Tests user registration, login, token management, and password operations.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.auth_service import (
    AuthService,
    pwd_context,
    SECRET_KEY,
    REFRESH_SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.errors import (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    ValidationError,
)


# ==================== Password Hashing Tests ====================

class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password_produces_hash(self):
        """Password hashing should produce a bcrypt hash."""
        password = "secure_password_123"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix
        assert len(hashed) == 60  # bcrypt hash length

    def test_same_password_different_hashes(self):
        """Same password should produce different hashes (salted)."""
        password = "secure_password_123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2  # Different salts

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        password = "secure_password_123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Incorrect password should fail verification."""
        password = "secure_password_123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password("wrong_password", hashed) is False

    def test_empty_password_can_be_hashed(self):
        """Empty password can be hashed (validation is caller's responsibility)."""
        hashed = AuthService.hash_password("")
        assert AuthService.verify_password("", hashed) is True


# ==================== Token Creation Tests ====================

class TestTokenCreation:
    """Test JWT token creation."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user object."""
        user = MagicMock()
        user.id = "user-123"
        user.username = "testuser"
        user.token_version = 1
        return user

    @pytest.fixture
    def auth_service(self):
        """Create auth service with mock session."""
        mock_session = AsyncMock()
        return AuthService(mock_session)

    def test_create_access_token_structure(self, auth_service, mock_user):
        """Access token should have correct structure."""
        token = auth_service.create_access_token(mock_user)

        # Decode without verification to check structure
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"
        assert payload["version"] == 1
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token_structure(self, auth_service, mock_user):
        """Refresh token should have correct structure."""
        token = auth_service.create_refresh_token(mock_user)

        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"
        assert payload["version"] == 1
        assert "exp" in payload

    def test_create_tokens_returns_pair(self, auth_service, mock_user):
        """create_tokens should return a TokenPair with both tokens."""
        tokens = auth_service.create_tokens(mock_user)

        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert tokens.token_type == "bearer"

    def test_access_token_expiration(self, auth_service, mock_user):
        """Access token should have correct expiration time."""
        token = auth_service.create_access_token(mock_user)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        exp_time = datetime.utcfromtimestamp(payload["exp"])
        iat_time = datetime.utcfromtimestamp(payload["iat"])

        # Should expire in ACCESS_TOKEN_EXPIRE_MINUTES
        expected_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        actual_delta = exp_time - iat_time

        # Allow 1 second tolerance
        assert abs((actual_delta - expected_delta).total_seconds()) < 1


# ==================== Token Validation Tests ====================

class TestTokenValidation:
    """Test token validation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock()
        user.id = "user-123"
        user.username = "testuser"
        user.token_version = 1
        user.is_active = True
        return user

    @pytest.fixture
    def auth_service(self, mock_session):
        """Create auth service."""
        return AuthService(mock_session)

    @pytest.fixture
    def valid_access_token(self, auth_service, mock_user):
        """Create a valid access token."""
        return auth_service.create_access_token(mock_user)

    @pytest.mark.asyncio
    async def test_validate_valid_token(self, auth_service, mock_user, valid_access_token):
        """Valid token should return user."""
        # Mock the database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        user = await auth_service.validate_access_token(valid_access_token)

        assert user.id == "user-123"
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_validate_expired_token(self, auth_service):
        """Expired token should raise TokenExpiredError."""
        # Create an expired token
        expire = datetime.utcnow() - timedelta(minutes=1)
        payload = {
            "sub": "user-123",
            "username": "testuser",
            "type": "access",
            "version": 1,
            "exp": expire,
            "iat": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            await auth_service.validate_access_token(expired_token)

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self, auth_service):
        """Invalid token should raise TokenInvalidError."""
        with pytest.raises(TokenInvalidError):
            await auth_service.validate_access_token("not.a.valid.token")

    @pytest.mark.asyncio
    async def test_validate_refresh_as_access(self, auth_service, mock_user):
        """Refresh token used as access token should fail."""
        refresh_token = auth_service.create_refresh_token(mock_user)

        with pytest.raises(TokenInvalidError):
            await auth_service.validate_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_validate_token_version_mismatch(self, auth_service, mock_user, valid_access_token):
        """Token with old version should be rejected."""
        # User has newer token version (e.g., after password change)
        mock_user.token_version = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(TokenExpiredError):
            await auth_service.validate_access_token(valid_access_token)


# ==================== Token Refresh Tests ====================

class TestTokenRefresh:
    """Test token refresh functionality."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "user-123"
        user.username = "testuser"
        user.token_version = 1
        return user

    @pytest.fixture
    def auth_service(self, mock_session):
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, auth_service, mock_user):
        """Valid refresh token should return new token pair."""
        refresh_token = auth_service.create_refresh_token(mock_user)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        new_tokens = await auth_service.refresh_tokens(refresh_token)

        assert new_tokens.access_token is not None
        assert new_tokens.refresh_token is not None

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, auth_service):
        """Expired refresh token should raise TokenExpiredError."""
        expire = datetime.utcnow() - timedelta(days=1)
        payload = {
            "sub": "user-123",
            "type": "refresh",
            "version": 1,
            "exp": expire,
        }
        expired_refresh = jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            await auth_service.refresh_tokens(expired_refresh)

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(self, auth_service, mock_user):
        """Access token used as refresh token should fail."""
        access_token = auth_service.create_access_token(mock_user)

        with pytest.raises(TokenInvalidError):
            await auth_service.refresh_tokens(access_token)


# ==================== User Registration Tests ====================

class TestUserRegistration:
    """Test user registration."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def auth_service(self, mock_session):
        return AuthService(mock_session)

    @pytest.fixture
    def user_create_data(self):
        data = MagicMock()
        data.username = "newuser"
        data.email = "newuser@example.com"
        data.password = "secure_password_123"
        data.display_name = "New User"
        return data

    @pytest.mark.asyncio
    async def test_register_new_user(self, auth_service, user_create_data):
        """Should register a new user successfully."""
        # Mock that no existing user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        user = await auth_service.register(user_create_data)

        assert auth_service.session.add.called
        assert auth_service.session.commit.called

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, auth_service, user_create_data):
        """Should reject duplicate username."""
        existing_user = MagicMock()
        existing_user.username = "newuser"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValidationError) as exc_info:
            await auth_service.register(user_create_data)

        assert "Username already taken" in str(exc_info.value)


# ==================== User Login Tests ====================

class TestUserLogin:
    """Test user login."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "user-123"
        user.username = "testuser"
        user.password_hash = AuthService.hash_password("correct_password")
        user.token_version = 1
        user.last_login = None
        return user

    @pytest.fixture
    def auth_service(self, mock_session):
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_user):
        """Valid credentials should return user and tokens."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        user, tokens = await auth_service.login("testuser", "correct_password")

        assert user.id == "user-123"
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service, mock_user):
        """Wrong password should raise InvalidCredentialsError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("testuser", "wrong_password")

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_service):
        """Nonexistent user should raise InvalidCredentialsError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("nonexistent", "password")

    @pytest.mark.asyncio
    async def test_login_updates_last_login(self, auth_service, mock_user):
        """Login should update last_login timestamp."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        await auth_service.login("testuser", "correct_password")

        assert mock_user.last_login is not None
        assert auth_service.session.commit.called


# ==================== Logout Tests ====================

class TestLogout:
    """Test logout functionality."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "user-123"
        user.token_version = 1
        return user

    @pytest.fixture
    def auth_service(self, mock_session):
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_logout_increments_token_version(self, auth_service, mock_user):
        """Logout should increment token version."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.logout("user-123")

        assert result is True
        assert mock_user.token_version == 2

    @pytest.mark.asyncio
    async def test_logout_invalidates_tokens(self, auth_service, mock_user):
        """Old tokens should be invalid after logout."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        # Create token before logout
        old_token = auth_service.create_access_token(mock_user)

        # Logout
        await auth_service.logout("user-123")

        # Token version is now 2, old token has version 1
        with pytest.raises(TokenExpiredError):
            await auth_service.validate_access_token(old_token)


# ==================== Password Change Tests ====================

class TestPasswordChange:
    """Test password change functionality."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "user-123"
        user.password_hash = AuthService.hash_password("old_password")
        user.token_version = 1
        user.updated_at = None
        return user

    @pytest.fixture
    def auth_service(self, mock_session):
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service, mock_user):
        """Valid password change should succeed."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.change_password(
            "user-123", "old_password", "new_password"
        )

        assert result is True
        assert mock_user.token_version == 2  # Invalidate old tokens
        assert AuthService.verify_password("new_password", mock_user.password_hash)

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, auth_service, mock_user):
        """Wrong old password should fail."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.change_password(
                "user-123", "wrong_old_password", "new_password"
            )
