from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Link(BaseModel):
    href: str
    rel: str
    type: str | None = None
    title: str | None = None


class FeatureQuery(BaseModel):
    collection_id: str
    bbox: list[float] | None = None
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=10_000)
    offset: int = Field(default=0, ge=0)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 4:
            raise ValueError("bbox must contain minx,miny,maxx,maxy")
        minx, miny, maxx, maxy = value
        if minx >= maxx or miny >= maxy:
            raise ValueError("bbox minimums must be smaller than maximums")
        return value


class NearestQuery(BaseModel):
    collection_id: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    category: str | None = None
    radius_meters: float | None = Field(default=None, gt=0, le=100_000)
    limit: int = Field(default=5, ge=1, le=100)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class MapContext(BaseModel):
    bbox: list[float] | None = None
    zoom: float | None = None
    visible_collections: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    map_context: MapContext | None = None


class ToolExecution(BaseModel):
    name: str
    arguments: dict[str, Any]
    summary: str


class ChatResponse(BaseModel):
    answer: str
    model: str
    tool_executions: list[ToolExecution] = Field(default_factory=list)
    feature_collection: dict[str, Any] | None = None
