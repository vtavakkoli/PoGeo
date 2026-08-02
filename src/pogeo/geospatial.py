from __future__ import annotations

import json
from typing import Any

from pogeo.catalog import Catalog, CollectionDefinition
from pogeo.database import Database
from pogeo.models import FeatureQuery, NearestQuery
from pogeo.sql import SQLBuilder


def _decode_geometry(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _row_to_feature(
    row: Any,
    collection: CollectionDefinition,
    *,
    include_distance: bool = False,
) -> dict[str, Any]:
    properties = {name: row[name] for name in collection.properties}
    if include_distance:
        properties["distance_meters"] = round(float(row["distance_meters"]), 2)
    return {
        "type": "Feature",
        "id": row[collection.id_column],
        "geometry": _decode_geometry(row["geometry"]),
        "properties": properties,
    }


class GeoService:
    def __init__(self, database: Database, catalog: Catalog, max_features: int) -> None:
        self.database = database
        self.catalog = catalog
        self.max_features = max_features

    def list_collections(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "itemType": "feature",
                "crs": [f"http://www.opengis.net/def/crs/EPSG/0/{item.srid}"],
                "geometryType": item.geometry_type,
                "properties": item.properties,
            }
            for item in self.catalog.list()
        ]

    def describe_collection(self, collection_id: str) -> dict[str, Any]:
        item = self.catalog.get(collection_id)
        return {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "schema": item.schema_name,
            "table": item.table,
            "idColumn": item.id_column,
            "geometryColumn": item.geometry_column,
            "geometryType": item.geometry_type,
            "srid": item.srid,
            "properties": item.properties,
            "maxLimit": item.max_limit,
        }

    async def query_features(self, request: FeatureQuery) -> dict[str, Any]:
        collection = self.catalog.get(request.collection_id)
        bounded = request.model_copy(update={"limit": min(request.limit, self.max_features)})
        prepared = SQLBuilder.feature_query(collection, bounded)
        rows = await self.database.fetch(prepared.sql, *prepared.parameters)
        features = [_row_to_feature(row, collection) for row in rows]
        return {
            "type": "FeatureCollection",
            "numberReturned": len(features),
            "features": features,
        }

    async def get_feature(self, collection_id: str, feature_id: int) -> dict[str, Any] | None:
        collection = self.catalog.get(collection_id)
        prepared = SQLBuilder.item_query(collection, feature_id)
        row = await self.database.fetchrow(prepared.sql, *prepared.parameters)
        if row is None:
            return None
        return _row_to_feature(row, collection)

    async def find_nearest(self, request: NearestQuery) -> dict[str, Any]:
        collection = self.catalog.get(request.collection_id)
        prepared = SQLBuilder.nearest_query(collection, request)
        rows = await self.database.fetch(prepared.sql, *prepared.parameters)
        features = [
            _row_to_feature(row, collection, include_distance=True) for row in rows
        ]
        return {
            "type": "FeatureCollection",
            "numberReturned": len(features),
            "features": features,
        }

    async def vector_tile(self, collection_id: str, z: int, x: int, y: int) -> bytes:
        collection = self.catalog.get(collection_id)
        prepared = SQLBuilder.tile_query(collection, z, x, y)
        value = await self.database.fetchval(prepared.sql, *prepared.parameters)
        return bytes(value or b"")
