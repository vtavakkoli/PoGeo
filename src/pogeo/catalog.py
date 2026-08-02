from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    schema_name: str = Field(alias="schema")
    table: str
    id_column: str = "id"
    geometry_column: str = "geom"
    geometry_type: str = "Geometry"
    srid: int = 4326
    properties: list[str] = Field(default_factory=list)
    default_limit: int = Field(default=100, ge=1)
    max_limit: int = Field(default=1000, ge=1, le=100_000)

    model_config = {"populate_by_name": True}

    @field_validator("id", "schema_name", "table", "id_column", "geometry_column")
    @classmethod
    def identifiers_are_safe(cls, value: str) -> str:
        return validate_identifier(value)

    @field_validator("properties")
    @classmethod
    def properties_are_safe(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Collection properties must be unique")
        return [validate_identifier(value) for value in values]

    @model_validator(mode="after")
    def limits_are_consistent(self) -> CollectionDefinition:
        if self.default_limit > self.max_limit:
            raise ValueError("default_limit must not exceed max_limit")
        return self

    @property
    def qualified_table(self) -> str:
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

    @classmethod
    def load(cls, path: Path) -> Catalog:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = CatalogFile.model_validate(payload)
        return cls(parsed.collections)

    def list(self) -> list[CollectionDefinition]:
        return sorted(self._collections.values(), key=lambda item: item.id)

    def get(self, collection_id: str) -> CollectionDefinition:
        try:
            return self._collections[collection_id]
        except KeyError as exc:
            raise KeyError(f"Unknown collection: {collection_id}") from exc
