"""Application configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings sourced from the environment.

    The repo-root ``.env`` is loaded when present. In production, values are
    supplied directly through the environment (see docker-compose in later
    milestones).
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LiveKit ──
    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")

    # ── Token / session ──
    token_ttl_seconds: int = Field(default=600, alias="TOKEN_TTL_SECONDS")

    # Name the agent worker registers under (used for explicit dispatch).
    agent_name: str = Field(default="voice-assistant-agent", alias="AGENT_NAME")

    # ── CORS ──
    backend_cors_origins: str = Field(
        default="http://localhost:5173", alias="BACKEND_CORS_ORIGINS"
    )

    # ── Rate limiting (Milestone 7) ──
    # Max calls to POST /api/voice/session per IP per time window.
    # Format is "count/period" e.g. "10/minute". Set to "" to disable.
    rate_limit_session: str = Field(default="10/minute", alias="RATE_LIMIT_SESSION")

    # ── Internal API auth (Milestone 7) ──
    # Shared secret the agent sends in X-Internal-Secret on /api/orders etc.
    # When empty (dev default) the check is skipped. In production, set a
    # random string (at least 32 chars) in both backend and agent .env.
    internal_api_secret: str = Field(default="", alias="INTERNAL_API_SECRET")

    # ── Database (Milestone 5) ──
    # Async SQLAlchemy URL. Defaults to the docker-compose Postgres.
    database_url: str = Field(
        default="postgresql+asyncpg://voice_assistant:voice_assistant@localhost:5432/voice_assistant",
        alias="DATABASE_URL",
    )

    # ── RAG / embeddings (Milestone 5) ──
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    # Dimension of text-embedding-3-small. Kept in config so the vector column
    # and query vectors stay in sync.
    embedding_dim: int = Field(default=1536, alias="EMBEDDING_DIM")

    @property
    def cors_origins(self) -> list[str]:
        """Parse the comma-separated CORS origins into a list."""
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def livekit_configured(self) -> bool:
        """True only when all LiveKit credentials are present."""
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)

    @property
    def embeddings_configured(self) -> bool:
        """True when an OpenAI key is present for embeddings/RAG."""
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
