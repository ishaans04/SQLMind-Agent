from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQLMIND_", env_file=".env", extra="ignore")

    database_path: Path = Field(default=Path("data/demo.db"))
    default_limit: int = Field(default=50, ge=1, le=500)
    nvidia_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NVIDIA_API_KEY", "SQLMIND_NVIDIA_API_KEY"),
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias=AliasChoices("NVIDIA_BASE_URL", "SQLMIND_NVIDIA_BASE_URL"),
    )
    nvidia_model: str = Field(
        default="meta/llama-3.1-8b-instruct",
        validation_alias=AliasChoices("NVIDIA_MODEL", "SQLMIND_NVIDIA_MODEL"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
