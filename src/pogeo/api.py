from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from fastapi.responses import ORJSONResponse

from pogeo.models import ChatRequest, ChatResponse, FeatureQuery, NearestQuery
from pogeo.ollama import OllamaAgent, OllamaUnavailableError
from pogeo.runtime import get_runtime

router = APIRouter(default_response_class=ORJSONResponse)

OGC_CONFORMANCE = [
    "urn:pogeo:conformance:features-read:0.1",
    "urn:pogeo:conformance:mapbox-vector-tiles:0.1",
]


def _parse_bbox(value: str | None) -> list[float] | None:
    if value is None:
        return None
    try:
        coordinates = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bbox must contain four numbers") from exc
    if len(coordinates) != 4:
        raise HTTPException(status_code=422, detail="bbox must contain four numbers")
    return coordinates


@router.get("/health", tags=["Operations"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pogeo"}


@router.get("/ready", tags=["Operations"])
async def ready() -> dict[str, str]:
    try:
        available = await get_runtime().database.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="PostGIS is unavailable") from exc
    return {"status": "ready" if available else "not-ready"}


@router.get("/api/ai/status", tags=["AI"])
async def ai_status(request: Request) -> dict[str, Any]:
    agent: OllamaAgent = request.app.state.ollama
    return await agent.status()


@router.post("/api/chat", response_model=ChatResponse, tags=["AI"])
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    agent: OllamaAgent = request.app.state.ollama
    try:
        return await agent.chat(payload)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/ogc", tags=["OGC API"])
async def ogc_landing() -> dict[str, Any]:
    return {
        "title": "PoGeo OGC-style API",
        "description": "PostGIS features and vector tiles exposed through PoGeo.",
        "links": [
            {"href": "/api/ogc", "rel": "self", "type": "application/json"},
            {"href": "/conformance", "rel": "conformance", "type": "application/json"},
            {"href": "/collections", "rel": "data", "type": "application/json"},
            {"href": "/docs", "rel": "service-doc", "type": "text/html"},
        ],
    }


@router.get("/conformance", tags=["OGC API"])
async def conformance() -> dict[str, list[str]]:
    return {"conformsTo": OGC_CONFORMANCE}


@router.get("/collections", tags=["OGC API"])
async def collections() -> dict[str, Any]:
    items = get_runtime().geo.list_collections()
    for item in items:
        collection_id = item["id"]
        item["links"] = [
            {
                "href": f"/collections/{collection_id}",
                "rel": "self",
                "type": "application/json",
            },
            {
                "href": f"/collections/{collection_id}/items",
                "rel": "items",
                "type": "application/geo+json",
            },
        ]
    return {"collections": items, "links": [{"href": "/collections", "rel": "self"}]}


@router.get("/collections/{collection_id}", tags=["OGC API"])
async def collection(collection_id: str) -> dict[str, Any]:
    try:
        item = get_runtime().geo.describe_collection(collection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    item["links"] = [
        {"href": f"/collections/{collection_id}", "rel": "self"},
        {
            "href": f"/collections/{collection_id}/items",
            "rel": "items",
            "type": "application/geo+json",
        },
        {
            "href": f"/collections/{collection_id}/tiles/{{z}}/{{x}}/{{y}}.pbf",
            "rel": "tiles",
            "type": "application/vnd.mapbox-vector-tile",
        },
    ]
    return item


@router.get("/collections/{collection_id}/items", tags=["OGC API"])
async def collection_items(
    collection_id: str,
    bbox: str | None = Query(default=None, description="minx,miny,maxx,maxy"),
    category: str | None = None,
    district: int | None = None,
    limit: int = Query(default=100, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters: dict[str, str | int | float | bool] = {}
    if category is not None:
        filters["category"] = category
    if district is not None:
        filters["district"] = district
    request = FeatureQuery(
        collection_id=collection_id,
        bbox=_parse_bbox(bbox),
        filters=filters,
        limit=limit,
        offset=offset,
    )
    try:
        result = await get_runtime().geo.query_features(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["links"] = [
        {
            "href": f"/collections/{collection_id}/items",
            "rel": "self",
            "type": "application/geo+json",
        }
    ]
    return result


@router.get("/collections/{collection_id}/items/{feature_id}", tags=["OGC API"])
async def collection_item(collection_id: str, feature_id: int) -> dict[str, Any]:
    try:
        feature = await get_runtime().geo.get_feature(collection_id, feature_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.get("/api/nearest", tags=["Spatial analysis"])
async def nearest(
    collection_id: str = "places",
    longitude: float = Query(ge=-180, le=180),
    latitude: float = Query(ge=-90, le=90),
    category: str | None = None,
    radius_meters: float | None = Query(default=None, gt=0, le=100_000),
    limit: int = Query(default=5, ge=1, le=100),
) -> dict[str, Any]:
    request = NearestQuery(
        collection_id=collection_id,
        longitude=longitude,
        latitude=latitude,
        category=category,
        radius_meters=radius_meters,
        limit=limit,
    )
    try:
        return await get_runtime().geo.find_nearest(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/collections/{collection_id}/tiles/{z}/{x}/{y}.pbf",
    tags=["Vector tiles"],
    response_class=Response,
)
async def vector_tile(
    collection_id: str,
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
) -> Response:
    max_coordinate = (1 << z) - 1
    if x > max_coordinate or y > max_coordinate:
        raise HTTPException(status_code=422, detail="Tile coordinates are outside this zoom")
    try:
        tile = await get_runtime().geo.vector_tile(collection_id, z, x, y)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=tile,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "public, max-age=300"},
        status_code=status.HTTP_200_OK,
    )
