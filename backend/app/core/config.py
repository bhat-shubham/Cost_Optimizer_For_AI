"""
Application settings loaded from environment variables.

Uses pydantic-settings so that every config value is validated at startup.
All secrets stay in .env on the server — never in frontend code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration.

    DATABASE_URL must use the asyncpg scheme:
        postgresql+asyncpg://user:pass@host:5432/dbname
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Required ────────────────────────────────────────────
    DATABASE_URL: str

    # ── Optional (sensible defaults) ────────────────────────
    APP_NAME: str = "AI Cost Optimizer"
    DEBUG: bool = False
    ENVIRONMENT: str = "dev"


# Singleton — imported everywhere as `from app.core.config import settings`
settings = Settings()  # type: ignore[call-arg]
