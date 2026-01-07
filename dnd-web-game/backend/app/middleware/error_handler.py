"""
D&D Combat Engine - Error Handler Middleware
Catches and formats all exceptions into structured JSON responses.
"""
import traceback
import logging
from typing import Callable
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import (
    GameError,
    ErrorCode,
    ValidationError as GameValidationError,
)

# Configure logging
logger = logging.getLogger("dnd_engine.errors")


class ErrorHandlerMiddleware:
    """
    Middleware that catches all exceptions and returns structured JSON responses.

    Features:
    - Converts all exceptions to JSON format
    - Logs errors with context
    - Provides recovery hints to frontend
    - Supports error tracking integration (Sentry-ready)
    """

    def __init__(self, app: FastAPI, debug: bool = False):
        self.app = app
        self.debug = debug

    async def __call__(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except Exception as exc:
            return await self.handle_exception(request, exc)

    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle any exception and return a structured JSON response."""

        # Log the error
        error_id = self._generate_error_id()
        self._log_error(request, exc, error_id)

        # Convert to GameError if not already
        if isinstance(exc, GameError):
            game_error = exc
        else:
            game_error = self._convert_to_game_error(exc)

        # Build response
        response_data = game_error.to_dict()
        response_data["error"]["error_id"] = error_id
        response_data["error"]["timestamp"] = datetime.utcnow().isoformat()

        # Add stack trace in debug mode
        if self.debug and not isinstance(exc, GameError):
            response_data["error"]["debug"] = {
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc().split("\n")
            }

        return JSONResponse(
            status_code=game_error.http_status,
            content=response_data
        )

    def _convert_to_game_error(self, exc: Exception) -> GameError:
        """Convert standard exceptions to GameError instances."""

        # FastAPI/Pydantic validation errors
        if isinstance(exc, (RequestValidationError, PydanticValidationError)):
            return self._handle_validation_error(exc)

        # Starlette HTTP exceptions
        if isinstance(exc, StarletteHTTPException):
            return GameError(
                code=self._http_status_to_error_code(exc.status_code),
                message=str(exc.detail) if exc.detail else "HTTP Error",
                http_status=exc.status_code
            )

        # Connection errors
        if isinstance(exc, ConnectionError):
            return GameError(
                code=ErrorCode.DATABASE_CONNECTION_FAILED,
                message="Connection error",
                http_status=503,
                recovery_hint="Please try again in a moment"
            )

        # Generic exception
        return GameError(
            code=ErrorCode.UNKNOWN,
            message="An unexpected error occurred" if not self.debug else str(exc),
            http_status=500,
            recoverable=False
        )

    def _handle_validation_error(self, exc: Exception) -> GameError:
        """Convert validation errors to structured format."""
        errors = []

        if isinstance(exc, RequestValidationError):
            for error in exc.errors():
                field = " -> ".join(str(loc) for loc in error.get("loc", []))
                errors.append({
                    "field": field,
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "validation_error")
                })
        elif isinstance(exc, PydanticValidationError):
            for error in exc.errors():
                field = " -> ".join(str(loc) for loc in error.get("loc", []))
                errors.append({
                    "field": field,
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "validation_error")
                })

        return GameError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Validation failed",
            details={"errors": errors},
            http_status=422,
            recovery_hint="Check the highlighted fields and correct the values"
        )

    def _http_status_to_error_code(self, status: int) -> ErrorCode:
        """Map HTTP status codes to error codes."""
        mapping = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTH_UNAUTHORIZED,
            403: ErrorCode.AUTH_FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            429: ErrorCode.AI_RATE_LIMITED,
            500: ErrorCode.UNKNOWN,
            503: ErrorCode.AI_SERVICE_UNAVAILABLE,
        }
        return mapping.get(status, ErrorCode.UNKNOWN)

    def _generate_error_id(self) -> str:
        """Generate a unique error ID for tracking."""
        import uuid
        return str(uuid.uuid4())[:8]

    def _log_error(self, request: Request, exc: Exception, error_id: str):
        """Log error with context."""
        log_data = {
            "error_id": error_id,
            "method": request.method,
            "path": str(request.url.path),
            "query": str(request.url.query),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }

        if isinstance(exc, GameError):
            log_data["error_code"] = exc.code.value
            logger.warning(f"[{error_id}] GameError: {exc.code.value} - {exc.message}", extra=log_data)
        else:
            logger.error(
                f"[{error_id}] Unhandled exception: {type(exc).__name__}: {exc}",
                extra=log_data,
                exc_info=True
            )


def setup_error_handlers(app: FastAPI, debug: bool = False):
    """
    Setup all error handlers for the FastAPI application.

    Call this function after creating the FastAPI app to register
    exception handlers for GameError and standard exceptions.
    """

    @app.exception_handler(GameError)
    async def game_error_handler(request: Request, exc: GameError):
        """Handle GameError exceptions."""
        error_id = str(__import__("uuid").uuid4())[:8]

        logger.warning(
            f"[{error_id}] GameError: {exc.code.value} - {exc.message}",
            extra={
                "error_id": error_id,
                "error_code": exc.code.value,
                "path": str(request.url.path),
            }
        )

        response_data = exc.to_dict()
        response_data["error"]["error_id"] = error_id
        response_data["error"]["timestamp"] = datetime.utcnow().isoformat()

        return JSONResponse(
            status_code=exc.http_status,
            content=response_data
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors from request parsing."""
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error.get("loc", []))
            errors.append({
                "field": field,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error")
            })

        error_id = str(__import__("uuid").uuid4())[:8]

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                    "recoverable": True,
                    "recovery_hint": "Check the request data and correct any invalid fields",
                    "error_id": error_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle standard HTTP exceptions."""
        error_id = str(__import__("uuid").uuid4())[:8]

        # Map status codes to error codes
        error_code_map = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTH_UNAUTHORIZED,
            403: ErrorCode.AUTH_FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            429: ErrorCode.AI_RATE_LIMITED,
            500: ErrorCode.UNKNOWN,
            503: ErrorCode.AI_SERVICE_UNAVAILABLE,
        }

        error_code = error_code_map.get(exc.status_code, ErrorCode.UNKNOWN)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code.value,
                    "message": str(exc.detail) if exc.detail else "An error occurred",
                    "details": {},
                    "recoverable": exc.status_code < 500,
                    "recovery_hint": None,
                    "error_id": error_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        error_id = str(__import__("uuid").uuid4())[:8]

        logger.error(
            f"[{error_id}] Unhandled exception: {type(exc).__name__}: {exc}",
            extra={
                "error_id": error_id,
                "path": str(request.url.path),
                "method": request.method,
            },
            exc_info=True
        )

        # Print to console for debugging
        print(f"\n{'='*70}")
        print(f"[ERROR {error_id}] Unhandled exception on {request.method} {request.url.path}")
        print(f"[ERROR {error_id}] {type(exc).__name__}: {exc}")
        if debug:
            traceback.print_exc()
        print(f"{'='*70}\n")

        content = {
            "error": {
                "code": ErrorCode.UNKNOWN.value,
                "message": "An unexpected error occurred",
                "details": {},
                "recoverable": False,
                "recovery_hint": "Please try again or contact support",
                "error_id": error_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Add debug info if in debug mode
        if debug:
            content["error"]["debug"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc().split("\n")
            }

        return JSONResponse(
            status_code=500,
            content=content
        )

    return app
