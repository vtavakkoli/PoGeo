import pytest

from pogeo.catalog import CollectionDefinition
from pogeo.models import FeatureQuery, NearestQuery
from pogeo.sql import SQLBuilder


@pytest.fixture
def collection() -> CollectionDefinition:
    return CollectionDefinition.model_validate(
        {
            "id": "places",
            "title": "Places",
            "schema": "pogeo",
            "table": "places",
            "id_column": "id",
            "geometry_column": "geom",
            "geography_column": "geom_geog",
            "properties": ["name", "category", "district"],
            "max_limit": 500,
        }
    )


def test_feature_query_parameterizes_values(collection: CollectionDefinition) -> None:
    request = FeatureQuery(
        collection_id="places",
        bbox=[16.2, 48.1, 16.5, 48.3],
        filters={"category": "museum' OR TRUE --", "district": 1},
        limit=1000,
    )

    prepared = SQLBuilder.feature_query(collection, request)

    assert "museum' OR TRUE --" not in prepared.sql
    assert 't."category"' in prepared.sql
    assert prepared.parameters[-2] == 500
    assert prepared.parameters[-1] == 0


def test_feature_query_rejects_non_allowlisted_filter(collection: CollectionDefinition) -> None:
    request = FeatureQuery(collection_id="places", filters={"secret": "value"})

    with pytest.raises(ValueError, match="not allowed"):
        SQLBuilder.feature_query(collection, request)


def test_nearest_query_uses_indexed_geography_and_knn(
    collection: CollectionDefinition,
) -> None:
    request = NearestQuery(
        collection_id="places",
        longitude=16.3731,
        latitude=48.2085,
        radius_meters=2500,
        limit=5,
    )

    prepared = SQLBuilder.nearest_query(collection, request)

    assert 'ST_DWithin(t."geom_geog"' in prepared.sql
    assert 't."geom" <-> ST_Transform' in prepared.sql
    assert "ST_Distance" in prepared.sql
    assert prepared.parameters == (16.3731, 48.2085, 2500.0, 5)


def test_tile_query_preserves_spatial_index_use(collection: CollectionDefinition) -> None:
    prepared = SQLBuilder.tile_query(collection, 12, 2234, 1422)

    assert 't."geom" && bounds.source' in prepared.sql
    assert 'ST_Intersects(t."geom", bounds.source)' in prepared.sql
    assert 'ST_Intersects(ST_Transform(t."geom"' not in prepared.sql
