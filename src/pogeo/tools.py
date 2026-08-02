from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from pogeo.models import FeatureQuery, NearestQuery
from pogeo.runtime import Runtime


@dataclass(slots=True)
class ToolResult:
    content: dict[str, Any] | list[dict[str, Any]]
    summary: str
    feature_collection: dict[str, Any] | None = None


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_collections",
            "description": "List the geospatial collections that PoGeo is allowed to query.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_collection",
            "description": "Describe one approved collection and its queryable properties.",
            "parameters": {
                "type": "object",
                "required": ["collection_id"],
                "properties": {
                    "collection_id": {
                        "type": "string",
                        "description": "Collection ID returned by list_collections.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_features",
            "description": (
                "Query an approved collection using an optional bounding box and exact-match "
                "property filters. Never invent property names."
            ),
            "parameters": {
                "type": "object",
                "required": ["collection_id"],
                "properties": {
                    "collection_id": {"type": "string"},
                    "bbox": {
                        "type": ["array", "null"],
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "filters": {
                        "type": "object",
                        "additionalProperties": {"type": ["string", "number", "boolean"]},
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "offset": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_nearest",
            "description": (
                "Find the nearest features to a WGS84 longitude and latitude, optionally "
                "restricted by category or radius."
            ),
            "parameters": {
                "type": "object",
                "required": ["collection_id", "longitude", "latitude"],
                "properties": {
                    "collection_id": {"type": "string"},
                    "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                    "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                    "category": {"type": ["string", "null"]},
                    "radius_meters": {
                        "type": ["number", "null"],
                        "exclusiveMinimum": 0,
                        "maximum": 100000,
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
        },
    },
]


class ToolRegistry:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            if name == "list_collections":
                collections = self.runtime.geo.list_collections()
                return ToolResult(
                    content=collections,
                    summary=f"Listed {len(collections)} published collection(s).",
                )

            if name == "describe_collection":
                collection_id = str(arguments["collection_id"])
                description = self.runtime.geo.describe_collection(collection_id)
                return ToolResult(
                    content=description,
                    summary=f"Described collection {collection_id!r}.",
                )

            if name == "query_features":
                request = FeatureQuery.model_validate(arguments)
                result = await self.runtime.geo.query_features(request)
                return ToolResult(
                    content=result,
                    summary=(
                        f"Returned {result['numberReturned']} feature(s) from "
                        f"{request.collection_id!r}."
                    ),
                    feature_collection=result,
                )

            if name == "find_nearest":
                request = NearestQuery.model_validate(arguments)
                result = await self.runtime.geo.find_nearest(request)
                return ToolResult(
                    content=result,
                    summary=(
                        f"Returned {result['numberReturned']} nearest feature(s) from "
                        f"{request.collection_id!r}."
                    ),
                    feature_collection=result,
                )
        except (KeyError, ValueError, ValidationError) as exc:
            raise ValueError(f"Invalid arguments for tool {name!r}: {exc}") from exc

        raise ValueError(f"Unknown PoGeo tool: {name}")
