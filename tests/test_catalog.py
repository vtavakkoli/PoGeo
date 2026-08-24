from pathlib import Path

import pytest

from pogeo.catalog import Catalog, CollectionDefinition, quote_identifier


def test_catalog_loads_default_configuration() -> None:
    catalog = Catalog.load(Path("config/collections.yaml"))
    collection = catalog.get("places")

    assert collection.title == "Vienna Places"
    assert collection.provider == "postgis"
    assert collection.qualified_table == '"pogeo"."places"'
    assert collection.geography_column == "geom_geog"
    assert "category" in collection.properties


def test_catalog_accepts_allowlisted_wfs_collection() -> None:
    collection = CollectionDefinition.model_validate(
        {
            "id": "playgrounds",
            "title": "Vienna playgrounds",
            "provider": "wfs",
            "wfs_url": "https://data.wien.gv.at/daten/geo",
            "wfs_type_name": "ogdwien:SPIELPLATZOGD",
            "properties": ["NAME", "BEZIRK"],
            "max_limit": 5000,
        }
    )

    assert collection.provider == "wfs"
    assert collection.wfs_type_name == "ogdwien:SPIELPLATZOGD"
    with pytest.raises(ValueError, match="only available for PostGIS"):
        _ = collection.qualified_table


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


def test_catalog_rejects_unsafe_wfs_configuration() -> None:
    with pytest.raises(ValueError, match="must not embed credentials"):
        CollectionDefinition.model_validate(
            {
                "id": "places",
                "title": "Places",
                "provider": "wfs",
                "wfs_url": "https://user:secret@example.com/wfs",
                "wfs_type_name": "demo:places",
            }
        )

    with pytest.raises(ValueError, match="namespace:name"):
        CollectionDefinition.model_validate(
            {
                "id": "places",
                "title": "Places",
                "provider": "wfs",
                "wfs_url": "https://example.com/wfs",
                "wfs_type_name": "demo:places;DROP",
            }
        )


def test_quote_identifier_only_accepts_simple_postgresql_names() -> None:
    assert quote_identifier("safe_name_2") == '"safe_name_2"'
    with pytest.raises(ValueError):
        quote_identifier('places"')
