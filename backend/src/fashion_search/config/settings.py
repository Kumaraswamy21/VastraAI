"""Environment-backed settings for the fashion search API."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    gemini_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:9b"
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 16
    embedding_max_retries: int = 3
    embedding_stale_processing_minutes: int = 30
    search_parser_model: str = Field(default="gemini-2.5-flash-lite", min_length=1)
    search_parser_temperature: float = Field(default=0.0, ge=0, le=2)
    search_parser_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    search_parser_max_retries: int = Field(default=1, ge=0, le=3)
    market_currency: str = Field(default="INR", pattern=r"^[A-Za-z]{3}$")
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    def cors_origin_list(self) -> list[str]:
        """Split the comma-separated CORS origin string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached settings instance."""
    return Settings()
