from pathlib import Path

import pytest

from pogeo.catalog import Catalog, CollectionDefinition, quote_identifier


def test_catalog_loads_default_configuration() -> None:
    catalog = Catalog.load(Path("config/collections.yaml"))
    collection = catalog.get("places")

    assert collection.title == "Vienna Places"
    assert collection.qualified_table == '"pogeo"."places"'
    assert collection.geography_column == "geom_geog"
    assert "category" in collection.properties


def test_catalog_rejects_unsafe_identifiers() -> None:
    with pytest.raises(ValueError, match="Unsafe PostgreSQL identifier"):
        CollectionDefinition.model_validate(
            {
                "id": "places",
                "title": "Places",
                "schema": "public; DROP SCHEMA public",
                "table": "places",
            }
        )


def test_quote_identifier_only_accepts_simple_postgresql_names() -> None:
    assert quote_identifier("safe_name_2") == '"safe_name_2"'
    with pytest.raises(ValueError):
        quote_identifier('places"')
