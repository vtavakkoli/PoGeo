from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pogeo.catalog import CollectionDefinition, quote_identifier
from pogeo.models import FeatureQuery, NearestQuery


@dataclass(frozen=True)
class PreparedQuery:
    sql: str
    parameters: tuple[Any, ...]


class SQLBuilder:
    @staticmethod
    def feature_query(collection: CollectionDefinition, request: FeatureQuery) -> PreparedQuery:
        limit = min(request.limit, collection.max_limit)
        selected = ",\n                ".join(
            f"t.{quote_identifier(column)}" for column in collection.selectable_columns
        )
        conditions: list[str] = []
        parameters: list[Any] = []

        if request.bbox is not None:
            parameters.extend(request.bbox)
            base = len(parameters) - 3
            conditions.append(
                "ST_Intersects("
                f"t.{quote_identifier(collection.geometry_column)}, "
                "ST_Transform("
                f"ST_MakeEnvelope(${base}, ${base + 1}, ${base + 2}, ${base + 3}, 4326), "
                f"{collection.srid}"
                ")"
                ")"
            )

        allowed_filters = set(collection.properties)
        for key, value in sorted(request.filters.items()):
            if key not in allowed_filters:
                raise ValueError(f"Filtering by {key!r} is not allowed")
            parameters.append(value)
            conditions.append(f"t.{quote_identifier(key)} = ${len(parameters)}")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        parameters.extend([limit, request.offset])
        limit_parameter = len(parameters) - 1
        offset_parameter = len(parameters)

        sql = f"""
            SELECT
                {selected},
                ST_AsGeoJSON(
                    ST_Transform(t.{quote_identifier(collection.geometry_column)}, 4326),
                    6
                )::jsonb AS geometry
            FROM {collection.qualified_table} AS t
            WHERE {where_clause}
            ORDER BY t.{quote_identifier(collection.id_column)}
            LIMIT ${limit_parameter}
            OFFSET ${offset_parameter}
        """.strip()
        return PreparedQuery(sql=sql, parameters=tuple(parameters))

    @staticmethod
    def item_query(collection: CollectionDefinition, feature_id: int) -> PreparedQuery:
        selected = ",\n                ".join(
            f"t.{quote_identifier(column)}" for column in collection.selectable_columns
        )
        sql = f"""
            SELECT
                {selected},
                ST_AsGeoJSON(
                    ST_Transform(t.{quote_identifier(collection.geometry_column)}, 4326),
                    6
                )::jsonb AS geometry
            FROM {collection.qualified_table} AS t
            WHERE t.{quote_identifier(collection.id_column)} = $1
        """.strip()
        return PreparedQuery(sql=sql, parameters=(feature_id,))

    @staticmethod
    def nearest_query(collection: CollectionDefinition, request: NearestQuery) -> PreparedQuery:
        selected = ",\n                ".join(
            f"t.{quote_identifier(column)}" for column in collection.selectable_columns
        )
        point = "ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography"
        geometry = (
            f"ST_Transform(t.{quote_identifier(collection.geometry_column)}, 4326)::geography"
        )
        conditions = ["TRUE"]
        parameters: list[Any] = [request.longitude, request.latitude]

        if request.category is not None:
            if "category" not in collection.properties:
                raise ValueError("This collection does not expose a category property")
            parameters.append(request.category)
            conditions.append(f"t.{quote_identifier('category')} = ${len(parameters)}")

        if request.radius_meters is not None:
            parameters.append(request.radius_meters)
            conditions.append(f"ST_DWithin({geometry}, {point}, ${len(parameters)})")

        parameters.append(min(request.limit, 100))
        sql = f"""
            SELECT
                {selected},
                ST_AsGeoJSON(
                    ST_Transform(t.{quote_identifier(collection.geometry_column)}, 4326),
                    6
                )::jsonb AS geometry,
                ST_Distance({geometry}, {point}) AS distance_meters
            FROM {collection.qualified_table} AS t
            WHERE {' AND '.join(conditions)}
            ORDER BY distance_meters
            LIMIT ${len(parameters)}
        """.strip()
        return PreparedQuery(sql=sql, parameters=tuple(parameters))

    @staticmethod
    def tile_query(collection: CollectionDefinition, z: int, x: int, y: int) -> PreparedQuery:
        properties = ", ".join(
            f"t.{quote_identifier(column)}" for column in collection.selectable_columns
        )
        geometry_column = quote_identifier(collection.geometry_column)
        sql = f"""
            WITH bounds AS (
                SELECT ST_TileEnvelope($1, $2, $3) AS geom
            ), tile_data AS (
                SELECT
                    {properties},
                    ST_AsMVTGeom(
                        ST_Transform(t.{geometry_column}, 3857),
                        bounds.geom,
                        4096,
                        64,
                        TRUE
                    ) AS geom
                FROM {collection.qualified_table} AS t
                CROSS JOIN bounds
                WHERE ST_Intersects(ST_Transform(t.{geometry_column}, 3857), bounds.geom)
                LIMIT 10000
            )
            SELECT ST_AsMVT(tile_data, $4, 4096, 'geom') FROM tile_data
        """.strip()
        return PreparedQuery(sql=sql, parameters=(z, x, y, collection.id))
