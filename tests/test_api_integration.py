from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.getenv("POGEO_TEST_BASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def base_url() -> str:
    if not BASE_URL:
        pytest.skip("POGEO_TEST_BASE_URL is not configured")
    return BASE_URL


def test_health_and_readiness(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=20) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/ready").json()["status"] == "ready"


def test_collection_discovery_and_geojson(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=20) as client:
        catalog = client.get("/collections")
        assert catalog.status_code == 200
        assert catalog.json()["collections"][0]["id"] == "places"

        response = client.get(
            "/collections/places/items",
            params={"category": "museum", "limit": 20},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "FeatureCollection"
        assert payload["numberReturned"] >= 3
        assert all(item["properties"]["category"] == "museum" for item in payload["features"])


def test_nearest_spatial_query(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=20) as client:
        response = client.get(
            "/api/nearest",
            params={
                "collection_id": "places",
                "longitude": 16.3731,
                "latitude": 48.2085,
                "limit": 3,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["numberReturned"] == 3
        distances = [item["properties"]["distance_meters"] for item in payload["features"]]
        assert distances == sorted(distances)


def test_vector_tile_cache_and_conditional_get(base_url: str) -> None:
    path = "/collections/places/tiles/12/2234/1422.pbf"
    with httpx.Client(base_url=base_url, timeout=20) as client:
        first = client.get(path)
        assert first.status_code == 200
        assert first.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
        assert first.headers["x-pogeo-cache"] == "MISS"
        etag = first.headers["etag"]

        second = client.get(path)
        assert second.status_code == 200
        assert second.headers["x-pogeo-cache"] == "HIT"

        not_modified = client.get(path, headers={"If-None-Match": etag})
        assert not_modified.status_code == 304

        stats = client.get("/api/performance").json()["tileCache"]
        assert stats["hits"] >= 2
        assert stats["misses"] >= 1
