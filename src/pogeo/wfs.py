from __future__ import annotations

import math
from typing import Any

import httpx

from pogeo.catalog import CollectionDefinition
from pogeo.models import FeatureQuery, NearestQuery


def _cql_literal(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def _representative_point(geometry: dict[str, Any] | None) -> tuple[float, float] | None:
    if not geometry:
        return None

    coordinates = geometry.get("coordinates")
    points: list[tuple[float, float]] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            points.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(coordinates)
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class WFSClient:
    def __init__(
        self,
        max_features: int,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.max_features = max_features
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "PoGeo/0.2 WFS provider"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def query_features(
        self,
        collection: CollectionDefinition,
        request: FeatureQuery,
    ) -> dict[str, Any]:
        if collection.provider != "wfs" or collection.wfs_url is None:
            raise ValueError("WFSClient requires a WFS collection")

        unknown_filters = set(request.filters) - set(collection.properties)
        if unknown_filters:
            names = ", ".join(sorted(unknown_filters))
            raise ValueError(f"Filters are not allowlisted for {collection.id!r}: {names}")

        limit = min(request.limit, collection.max_limit, self.max_features)
        params: dict[str, str | int] = {
            "service": "WFS",
            "request": "GetFeature",
            "version": collection.wfs_version,
            "typeName": collection.wfs_type_name or "",
            "srsName": collection.wfs_srs_name,
            "outputFormat": collection.wfs_output_format,
            "maxFeatures": limit,
        }
        if request.offset:
            params["startIndex"] = request.offset
        if request.bbox is not None:
            params["bbox"] = ",".join(str(value) for value in request.bbox)
        if request.filters:
            params["CQL_FILTER"] = " AND ".join(
                f"{name}={_cql_literal(value)}" for name, value in sorted(request.filters.items())
            )

        response = await self._client.get(collection.wfs_url, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise ValueError("WFS endpoint did not return a GeoJSON FeatureCollection")

        features = [self._normalize_feature(item, collection) for item in payload["features"][:limit]]
        return {
            "type": "FeatureCollection",
            "numberReturned": len(features),
            "features": features,
        }

    async def find_nearest(
        self,
        collection: CollectionDefinition,
        request: NearestQuery,
    ) -> dict[str, Any]:
        search_radius = request.radius_meters or collection.wfs_nearest_radius_meters
        latitude_delta = search_radius / 110_540
        longitude_scale = max(math.cos(math.radians(request.latitude)), 0.05)
        longitude_delta = search_radius / (111_320 * longitude_scale)
        bbox = [
            request.longitude - longitude_delta,
            request.latitude - latitude_delta,
            request.longitude + longitude_delta,
            request.latitude + latitude_delta,
        ]

        filters: dict[str, str | int | float | bool] = {}
        if request.category is not None:
            if "category" not in collection.properties:
                raise ValueError(f"Collection {collection.id!r} does not expose a category property")
            filters["category"] = request.category

        candidate_limit = min(
            collection.max_limit,
            self.max_features,
            max(request.limit * 50, 500),
        )
        candidates = await self.query_features(
            collection,
            FeatureQuery(
                collection_id=collection.id,
                bbox=bbox,
                filters=filters,
                limit=candidate_limit,
            ),
        )

        ranked: list[tuple[float, dict[str, Any]]] = []
        for feature in candidates["features"]:
            point = _representative_point(feature.get("geometry"))
            if point is None:
                continue
            distance = _haversine_meters(
                request.longitude,
                request.latitude,
                point[0],
                point[1],
            )
            if request.radius_meters is not None and distance > request.radius_meters:
                continue
            properties = dict(feature.get("properties") or {})
            properties["distance_meters"] = round(distance, 2)
            ranked.append((distance, {**feature, "properties": properties}))

        ranked.sort(key=lambda item: item[0])
        features = [feature for _, feature in ranked[: request.limit]]
        return {
            "type": "FeatureCollection",
            "numberReturned": len(features),
            "features": features,
        }

    @staticmethod
    def _normalize_feature(
        feature: dict[str, Any],
        collection: CollectionDefinition,
    ) -> dict[str, Any]:
        source_properties = feature.get("properties") or {}
        properties = {
            name: source_properties[name]
            for name in collection.properties
            if name in source_properties
        }
        return {
            "type": "Feature",
            "id": feature.get("id"),
            "geometry": feature.get("geometry"),
            "properties": properties,
        }
