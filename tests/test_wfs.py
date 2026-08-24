from __future__ import annotations

import httpx
import pytest

from pogeo.catalog import CollectionDefinition
from pogeo.models import FeatureQuery, NearestQuery
from pogeo.wfs import WFSClient


def _collection() -> CollectionDefinition:
    return CollectionDefinition.model_validate(
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


@pytest.mark.asyncio
async def test_wfs_query_builds_bounded_geojson_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["service"] == "WFS"
        assert request.url.params["request"] == "GetFeature"
        assert request.url.params["typeName"] == "ogdwien:SPIELPLATZOGD"
        assert request.url.params["bbox"] == "16.3,48.2,16.4,48.3"
        assert request.url.params["CQL_FILTER"] == "BEZIRK=21"
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "playgrounds.1",
                        "geometry": {"type": "Point", "coordinates": [16.36, 48.25]},
                        "properties": {"NAME": "Test playground", "BEZIRK": 21, "SECRET": "drop"},
                    }
                ],
            },
        )

    client = WFSClient(max_features=1000, transport=httpx.MockTransport(handler))
    try:
        result = await client.query_features(
            _collection(),
            FeatureQuery(
                collection_id="playgrounds",
                bbox=[16.3, 48.2, 16.4, 48.3],
                filters={"BEZIRK": 21},
                limit=20,
            ),
        )
    finally:
        await client.close()

    assert result["numberReturned"] == 1
    assert result["features"][0]["properties"] == {
        "NAME": "Test playground",
        "BEZIRK": 21,
    }


@pytest.mark.asyncio
async def test_wfs_nearest_ranks_features_by_distance() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "far",
                        "geometry": {"type": "Point", "coordinates": [16.40, 48.25]},
                        "properties": {"NAME": "Far", "BEZIRK": 21},
                    },
                    {
                        "type": "Feature",
                        "id": "near",
                        "geometry": {"type": "Point", "coordinates": [16.361, 48.251]},
                        "properties": {"NAME": "Near", "BEZIRK": 21},
                    },
                ],
            },
        )

    client = WFSClient(max_features=1000, transport=httpx.MockTransport(handler))
    try:
        result = await client.find_nearest(
            _collection(),
            NearestQuery(
                collection_id="playgrounds",
                longitude=16.36,
                latitude=48.25,
                limit=2,
            ),
        )
    finally:
        await client.close()

    assert [feature["id"] for feature in result["features"]] == ["near", "far"]
    assert result["features"][0]["properties"]["distance_meters"] > 0


@pytest.mark.asyncio
async def test_wfs_rejects_non_allowlisted_filters() -> None:
    client = WFSClient(
        max_features=1000, transport=httpx.MockTransport(lambda _: httpx.Response(500))
    )
    try:
        with pytest.raises(ValueError, match="not allowlisted"):
            await client.query_features(
                _collection(),
                FeatureQuery(collection_id="playgrounds", filters={"SECRET": "x"}),
            )
    finally:
        await client.close()
