from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POGEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PoGeo"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://pogeo:pogeo@localhost:5432/pogeo"
    catalog_path: Path = Path("config/collections.yaml")
    web_path: Path = Path("web")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = Field(default=180.0, gt=0)
    max_features: int = Field(default=1000, ge=1, le=100_000)
    max_tool_iterations: int = Field(default=5, ge=1, le=12)
    cors_origins: str = "http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
