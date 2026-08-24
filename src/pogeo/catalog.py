from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WFS_TYPE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:[A-Za-z_][A-Za-z0-9_.-]*$")


def validate_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe PostgreSQL identifier: {value!r}")
    return value


def quote_identifier(value: str) -> str:
    return f'"{validate_identifier(value)}"'


class CollectionDefinition(BaseModel):
    id: str
    title: str
    description: str = ""
    provider: Literal["postgis", "wfs"] = "postgis"

    schema_name: str | None = Field(default=None, alias="schema")
    table: str | None = None
    id_column: str = "id"
    geometry_column: str = "geom"
    geography_column: str | None = None

    wfs_url: str | None = None
    wfs_type_name: str | None = None
    wfs_version: str = "1.1.0"
    wfs_srs_name: str = "EPSG:4326"
    wfs_output_format: str = "json"
    wfs_nearest_radius_meters: float = Field(default=50_000, gt=0, le=1_000_000)

    geometry_type: str = "Geometry"
    srid: int = 4326
    properties: list[str] = Field(default_factory=list)
    default_limit: int = Field(default=100, ge=1)
    max_limit: int = Field(default=1000, ge=1, le=100_000)

    model_config = {"populate_by_name": True}

    @field_validator("id", "id_column", "geometry_column")
    @classmethod
    def identifiers_are_safe(cls, value: str) -> str:
        return validate_identifier(value)

    @field_validator("schema_name", "table", "geography_column")
    @classmethod
    def optional_identifiers_are_safe(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value is not None else None

    @field_validator("properties")
    @classmethod
    def properties_are_safe(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Collection properties must be unique")
        return [validate_identifier(value) for value in values]

    @field_validator("wfs_url")
    @classmethod
    def wfs_url_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("wfs_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("wfs_url must not embed credentials")
        return value.rstrip("?")

    @field_validator("wfs_type_name")
    @classmethod
    def wfs_type_name_is_safe(cls, value: str | None) -> str | None:
        if value is not None and not _WFS_TYPE_NAME.fullmatch(value):
            raise ValueError("wfs_type_name must be a simple namespace:name identifier")
        return value

    @model_validator(mode="after")
    def provider_configuration_is_consistent(self) -> CollectionDefinition:
        if self.default_limit > self.max_limit:
            raise ValueError("default_limit must not exceed max_limit")
        if self.provider == "postgis":
            if self.schema_name is None or self.table is None:
                raise ValueError("PostGIS collections require schema and table")
        elif self.wfs_url is None or self.wfs_type_name is None:
            raise ValueError("WFS collections require wfs_url and wfs_type_name")
        return self

    @property
    def qualified_table(self) -> str:
        if self.provider != "postgis" or self.schema_name is None or self.table is None:
            raise ValueError("qualified_table is only available for PostGIS collections")
        return f"{quote_identifier(self.schema_name)}.{quote_identifier(self.table)}"

    @property
    def selectable_columns(self) -> list[str]:
        return [self.id_column, *self.properties]


class CatalogFile(BaseModel):
    collections: list[CollectionDefinition]


class Catalog:
    def __init__(self, collections: list[CollectionDefinition]) -> None:
        self._collections = {collection.id: collection for collection in collections}
        if len(self._collections) != len(collections):
            raise ValueError("Collection IDs must be unique")
        self._ordered_collections = tuple(
            sorted(self._collections.values(), key=lambda item: item.id)
        )

    @classmethod
    def load(cls, path: Path) -> Catalog:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = CatalogFile.model_validate(payload)
        return cls(parsed.collections)

    def list(self) -> tuple[CollectionDefinition, ...]:
        return self._ordered_collections

    def get(self, collection_id: str) -> CollectionDefinition:
        try:
            return self._collections[collection_id]
        except KeyError as exc:
            raise KeyError(f"Unknown collection: {collection_id}") from exc
