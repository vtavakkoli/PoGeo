# Changelog

All notable changes to PoGeo are documented here.

## [0.1.1] - 2026-08-02

### Fixed

- Pinned the supported MCP Python SDK v1 line, restoring the FastMCP import and container startup.
- Applied Ruff formatting to the source and integration tests.
- Added an application import smoke test to catch dependency/API incompatibilities before Compose.

### Performance

- Added a bounded TTL cache for Mapbox Vector Tiles with ETag and conditional GET support.
- Preserved PostGIS GiST index use for tile envelope and nearest-neighbour queries.
- Added an indexed generated geography column for accurate radius and distance operations.
- Made the asyncpg pool, statement timeout, idle lifetime, and cache limits configurable.
- Enabled response compression, optimized Uvicorn protocol implementations, and server timing headers.

## [0.1.0] - 2026-08-02

### Added

- FastAPI application with health, readiness, OpenAPI, and Prometheus endpoints.
- PostGIS-backed collection discovery, GeoJSON features, nearest-neighbour search, and MVT tiles.
- Streamable HTTP MCP server with tools, resources, and a geospatial prompt.
- Safe Ollama tool-calling agent with bounded iterations and no arbitrary SQL.
- Responsive map-and-chat demonstration web application.
- Docker Compose stack for PoGeo, PostGIS, Ollama, model provisioning, and integration tests.
- Ruff, pytest, coverage, HTML test reports, and GitHub Actions CI.
- Apache-2.0 license, architecture documentation, security policy, and contribution guide.
