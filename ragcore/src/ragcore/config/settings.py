"""Configuration. Pydantic Settings owns it; environment reads never scatter into business code."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated at startup so a missing value fails the process.

    Secret material resolves through managed identity and Key Vault, never from a committed
    file and never from source.
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNTHIA_",
        env_file=None,
        extra="forbid",
        frozen=True,
    )

    environment: str = "local"
    """Deployment environment name. Never used to make an authorization decision."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated settings singleton.

    Returns:
        The settings instance, constructed and validated on first call.
    """
    return Settings()
