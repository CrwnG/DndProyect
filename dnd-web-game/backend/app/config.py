"""Application configuration using environment variables."""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./game.db")

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS - Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Game Constants
    GRID_SIZE: int = 8  # 8x8 combat grid
    FEET_PER_SQUARE: int = 5  # Each grid square = 5 feet


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


_DEV_JWT_DEFAULTS = {
    "",
    "dev-secret-key-change-in-production",
    "dev-refresh-secret-key-change-in-production",
}


def check_jwt_secrets(jwt_secret: str, jwt_refresh_secret: str) -> list:
    """Return security warnings for weak/default JWT secrets.

    Does NOT raise (local/dev startup is never blocked); the app logs these at
    startup. Set strong JWT_SECRET_KEY/JWT_REFRESH_SECRET_KEY before deploying.
    """
    warnings = []
    if jwt_secret in _DEV_JWT_DEFAULTS:
        warnings.append("JWT_SECRET_KEY is unset or the public dev default — set a strong secret before any non-local deployment.")
    if jwt_refresh_secret in _DEV_JWT_DEFAULTS:
        warnings.append("JWT_REFRESH_SECRET_KEY is unset or the public dev default — set a strong secret before any non-local deployment.")
    return warnings
