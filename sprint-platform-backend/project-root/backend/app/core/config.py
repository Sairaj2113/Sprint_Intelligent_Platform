"""
Application configuration.

Settings are loaded from environment variables (see .env.example).
No secrets are hard-coded here.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables / .env file."""

    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@db:5432/sprint_intelligence"
    )

    PROJECT_NAME: str = "Sprint Management Platform"
    ENVIRONMENT: str = "local"
    DOCUMENT_STORAGE_ROOT: Path = Path("/app/storage/documents")
    MAX_DOCUMENT_SIZE_MB: int = 20
    DOCUMENT_CHUNK_SIZE_WORDS: int = 400
    DOCUMENT_CHUNK_OVERLAP_WORDS: int = 60
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_NORMALIZE: bool = True
    GROQ_API_KEY: SecretStr | None = None
    GEMINI_API_KEY: SecretStr | None = None
    GROQ_MODEL_NAME: str = "openai/gpt-oss-20b"
    GEMINI_MODEL_NAME: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
