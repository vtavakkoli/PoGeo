from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    database_pool_min_size: int = Field(default=2, ge=1, le=100)
    database_pool_max_size: int = Field(default=20, ge=1, le=200)
    database_statement_timeout_ms: int = Field(default=15_000, ge=100, le=300_000)
    database_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    database_max_queries_per_connection: int = Field(default=50_000, ge=100, le=1_000_000)
    database_max_idle_seconds: float = Field(default=300.0, ge=0, le=86_400)
    catalog_path: Path = Path("config/collections.yaml")
    web_path: Path = Path("web")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = Field(default=180.0, gt=0)
    max_features: int = Field(default=1000, ge=1, le=100_000)
    max_tool_iterations: int = Field(default=5, ge=1, le=12)
    tile_cache_max_items: int = Field(default=2048, ge=1, le=100_000)
    tile_cache_ttl_seconds: float = Field(default=300.0, gt=0, le=86_400)
    gzip_minimum_size: int = Field(default=1024, ge=0, le=1_000_000)
    cors_origins: str = "http://localhost:8000"

    @model_validator(mode="after")
    def validate_pool_sizes(self) -> Settings:
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("database_pool_min_size must not exceed database_pool_max_size")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
