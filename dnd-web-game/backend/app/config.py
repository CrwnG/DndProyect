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
