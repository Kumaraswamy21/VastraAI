"""Environment-backed settings for the fashion search API."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
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
    generation_provider: str = Field(default="gemini", pattern=r"^(gemini|ollama)$")
    generation_fallback_provider: str | None = Field(
        default=None, pattern=r"^(gemini|ollama)$"
    )
    generation_model: str | None = None
    generation_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    generation_max_retries: int = Field(default=1, ge=0, le=3)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:9b"
    ollama_generation_model: str = Field(default="gemma2:9b", min_length=1)
    ollama_embedding_model: str = Field(default="nomic-embed-text", min_length=1)
    ollama_embedding_dimensions: int = Field(default=768, ge=1)
    ollama_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    embedding_provider: str = Field(default="gemini", pattern=r"^(gemini|ollama)$")
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 16
    embedding_max_retries: int = 3
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    embedding_stale_processing_minutes: int = 30
    search_parser_model: str = Field(default="gemini-2.5-flash-lite", min_length=1)
    search_parser_temperature: float = Field(default=0.0, ge=0, le=2)
    search_parser_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    search_parser_max_retries: int = Field(default=1, ge=0, le=3)
    hybrid_rrf_k: int = Field(default=60, ge=1, le=500)
    hybrid_semantic_weight: float = Field(default=0.6, gt=0, le=1)
    hybrid_keyword_weight: float = Field(default=0.4, gt=0, le=1)
    hybrid_candidate_limit: int = Field(default=100, ge=10, le=500)
    search_strong_semantic_threshold: float = Field(default=0.75, ge=-1, le=1)
    search_weak_semantic_threshold: float = Field(default=0.35, ge=-1, le=1)
    search_min_keyword_signal: float = Field(default=0.01, ge=0)
    search_diagnostics_enabled: bool = True
    market_currency: str = Field(default="INR", pattern=r"^[A-Za-z]{3}$")
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @field_validator("generation_fallback_provider", mode="before")
    @classmethod
    def blank_fallback_is_disabled(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_search_quality_thresholds(self) -> "Settings":
        """Keep weak and strong semantic bands ordered."""
        if self.search_weak_semantic_threshold > self.search_strong_semantic_threshold:
            raise ValueError(
                "SEARCH_WEAK_SEMANTIC_THRESHOLD cannot exceed "
                "SEARCH_STRONG_SEMANTIC_THRESHOLD"
            )
        return self

    def cors_origin_list(self) -> list[str]:
        """Split the comma-separated CORS origin string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached settings instance."""
    return Settings()
