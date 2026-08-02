from __future__ import annotations

import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, ORJSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from pogeo import __version__
from pogeo.api import router
from pogeo.catalog import Catalog
from pogeo.config import get_settings
from pogeo.database import Database
from pogeo.geospatial import GeoService
from pogeo.mcp_server import mcp
from pogeo.ollama import OllamaAgent
from pogeo.runtime import Runtime, set_runtime

REQUESTS = Counter(
    "pogeo_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "pogeo_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    catalog = Catalog.load(settings.catalog_path)
    database = Database(
        settings.database_url,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        statement_timeout_ms=settings.database_statement_timeout_ms,
        connect_timeout_seconds=settings.database_connect_timeout_seconds,
        max_queries_per_connection=settings.database_max_queries_per_connection,
        max_idle_seconds=settings.database_max_idle_seconds,
    )
    await database.connect()
    geo = GeoService(
        database,
        catalog,
        settings.max_features,
        tile_cache_max_items=settings.tile_cache_max_items,
        tile_cache_ttl_seconds=settings.tile_cache_ttl_seconds,
    )
    runtime = Runtime(settings=settings, catalog=catalog, database=database, geo=geo)
    set_runtime(runtime)
    app.state.runtime = runtime
    app.state.ollama = OllamaAgent(runtime)

    async with mcp.session_manager.run():
        try:
            yield
        finally:
            await app.state.ollama.close()
            await database.close()
            set_runtime(None)


settings = get_settings()
app = FastAPI(
    title="PoGeo",
    summary="AI-native, MCP-ready PostGIS server",
    description=(
        "PoGeo publishes allowlisted PostGIS data through REST/OGC-style APIs, vector tiles, "
        "MCP tools, and a safe Ollama geospatial assistant."
    ),
    version=__version__,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "Mcp-Session-Id",
        "Last-Event-ID",
        "If-None-Match",
    ],
    expose_headers=["Mcp-Session-Id", "X-Request-ID", "ETag", "Server-Timing"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    elapsed = time.perf_counter() - started
    LATENCY.labels(request.method, route_path).observe(elapsed)
    REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(router)
app.mount("/mcp", mcp.streamable_http_app(), name="mcp")

web_path = settings.web_path
if not web_path.is_absolute():
    project_root = Path(__file__).resolve().parents[2]
    web_path = project_root / web_path
app.mount("/static", StaticFiles(directory=web_path), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(web_path / "index.html")


def run() -> None:
    uvicorn.run(  # noqa: S104
        "pogeo.main:app",
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        loop="uvloop",
        http="httptools",
        access_log=False,
    )


if __name__ == "__main__":
    run()
