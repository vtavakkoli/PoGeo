from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from pogeo.models import FeatureQuery, NearestQuery
from pogeo.runtime import get_runtime

mcp = FastMCP(
    name="PoGeo",
    instructions=(
        "Securely inspect and query the PostGIS collections published by PoGeo. "
        "Use list_collections before querying unfamiliar data. "
        "Raw SQL is intentionally unavailable."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@mcp.tool()
async def list_collections() -> list[dict[str, Any]]:
    """List every geospatial collection approved for querying."""
    return get_runtime().geo.list_collections()


@mcp.tool()
async def describe_collection(collection_id: str) -> dict[str, Any]:
    """Describe one collection, including geometry, CRS, and allowed properties."""
    return get_runtime().geo.describe_collection(collection_id)


@mcp.tool()
async def query_features(
    collection_id: str,
    bbox: list[float] | None = None,
    filters: dict[str, str | int | float | bool] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Query approved features using a bounding box and exact-match property filters."""
    request = FeatureQuery(
        collection_id=collection_id,
        bbox=bbox,
        filters=filters or {},
        limit=limit,
        offset=offset,
    )
    return await get_runtime().geo.query_features(request)


@mcp.tool()
async def find_nearest(
    collection_id: str,
    longitude: float,
    latitude: float,
    category: str | None = None,
    radius_meters: float | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Find the nearest approved features to a WGS84 coordinate."""
    request = NearestQuery(
        collection_id=collection_id,
        longitude=longitude,
        latitude=latitude,
        category=category,
        radius_meters=radius_meters,
        limit=limit,
    )
    return await get_runtime().geo.find_nearest(request)


@mcp.resource("pogeo://catalog")
async def catalog_resource() -> str:
    """Return the complete public PoGeo catalog as JSON."""
    return json.dumps(get_runtime().geo.list_collections(), ensure_ascii=False, indent=2)


@mcp.resource("pogeo://collections/{collection_id}")
async def collection_resource(collection_id: str) -> str:
    """Return one public collection definition as JSON."""
    return json.dumps(
        get_runtime().geo.describe_collection(collection_id),
        ensure_ascii=False,
        indent=2,
    )


@mcp.prompt()
def analyze_area(question: str, longitude: float, latitude: float) -> str:
    """Create a safe prompt for analysing an area around a coordinate."""
    return (
        f"Answer this geospatial question: {question}\n"
        f"Reference coordinate: longitude={longitude}, latitude={latitude}.\n"
        "List collections first, use only PoGeo tools, and cite returned feature counts."
    )
