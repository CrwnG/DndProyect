"""Middleware package for the D&D Combat Engine."""

from app.middleware.error_handler import ErrorHandlerMiddleware, setup_error_handlers
from app.middleware.auth import (
    get_current_user,
    get_current_user_optional,
    require_auth,
    optional_auth,
    authenticate_websocket,
)

__all__ = [
    "ErrorHandlerMiddleware",
    "setup_error_handlers",
    "get_current_user",
    "get_current_user_optional",
    "require_auth",
    "optional_auth",
    "authenticate_websocket",
]
