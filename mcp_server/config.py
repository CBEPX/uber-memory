"""
Application configuration from environment. Validated at startup.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP server settings. Loaded from environment with sensible defaults for local dev."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qdrant_url: str = Field(default="http://127.0.0.1:6333", validation_alias="QDRANT_URL")
    memgraph_bolt_uri: str = Field(
        default="bolt://127.0.0.1:7687", validation_alias="MEMGRAPH_BOLT_URI"
    )
    memory_collection: str = Field(default="project_memory", validation_alias="MEMORY_COLLECTION")
    embedding_dim: int = Field(default=384, validation_alias="EMBEDDING_DIM")
    memory_resource_max_chars: int = Field(default=40000, validation_alias="MEMORY_RESOURCE_MAX_CHARS")


def get_settings() -> Settings:
    """Return validated settings singleton."""
    if _settings is None:
        raise RuntimeError("Settings not initialized; call init_settings() first.")
    return _settings


def init_settings() -> Settings:
    """Load and validate settings. Call once at server startup."""
    global _settings
    _settings = Settings()
    return _settings


_settings: Settings | None = None

__all__ = ["Settings", "get_settings", "init_settings"]
