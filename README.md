<div align="center">

# PoGeo

**Spatial intelligence for PostGIS — in Rust.**

[![CI](https://github.com/vtavakkoli/AutoUpdate/actions/workflows/ci.yml/badge.svg)](https://github.com/vtavakkoli/AutoUpdate/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.88%2B-orange.svg)](rust-toolchain.toml)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-50e3b4.svg)](#mcp)

PoGeo is an AI-native, MCP-ready geospatial API server that exposes **allowlisted PostGIS data** through OGC-style GeoJSON APIs, safe spatial tools, and a polished Ollama-powered map application.

</div>

## Why PoGeo?

PoGeo is intentionally smaller and more focused than a complete GeoServer replacement:

- **PostGIS-native:** spatial filtering, distance, indexing, and GeoJSON generation remain in PostGIS.
- **Safe by construction:** users and models select only published collections and typed operations; there is no raw-SQL tool.
- **MCP-ready:** AI clients can discover and invoke geospatial tools over Streamable HTTP at `/mcp`.
- **Private AI:** the example application uses a local Ollama model with tool calling.
- **Cloud friendly:** one Rust binary, a read-only runtime container, health checks, structured logs, and graceful shutdown.
- **OGC-oriented:** collection discovery and feature endpoints follow the shape of OGC API Features.

## Included MVP

| Capability | Endpoint |
|---|---|
| Service metadata | `GET /` |
| Health/readiness | `GET /health` |
| OGC-style catalog | `GET /collections` |
| Collection metadata | `GET /collections/{id}` |
| GeoJSON features | `GET /collections/{id}/items` |
| Feature lookup | `GET /collections/{id}/items/{featureId}` |
| Proximity search | `GET /collections/{id}/nearby` |
| Collection statistics | `GET /collections/{id}/statistics` |
| Ollama spatial chat | `POST /api/chat` |
| MCP Streamable HTTP | `/mcp` |
| Interactive web demo | `/demo` |
| OpenAPI document | `/openapi.json` |

## Run the complete example

Requirements: Docker with Compose v2 and enough resources for the selected Ollama model.

```bash
cp .env.example .env
docker compose up --build
```

The first startup downloads `${OLLAMA_MODEL:-qwen3:4b}`. Then open:

- Web application: <http://localhost:8080/demo>
- PoGeo API: <http://localhost:8080>
- MCP endpoint: <http://localhost:8080/mcp>
- PostGIS: `localhost:5432`
- Ollama: <http://localhost:11434>

Run the API smoke test:

```bash
./scripts/smoke-test.sh
```

Reset all persistent demonstration data and downloaded models:

```bash
make reset
```

## Example API calls

```bash
# Discover approved datasets
curl http://localhost:8080/collections

# Query features in a WGS84 bounding box
curl 'http://localhost:8080/collections/vienna_places/items?bbox=16.30,48.17,16.43,48.24&limit=20'

# Find stations within one kilometre of Stephansplatz
curl 'http://localhost:8080/collections/vienna_stations/nearby?longitude=16.3717&latitude=48.2082&distanceMeters=1000&limit=10'

# Ask the local model
curl http://localhost:8080/api/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Find stations within one kilometre of Stephansplatz"}'
```

## MCP

PoGeo exposes these read-only tools:

- `list_collections`
- `query_features`
- `find_nearby`
- `collection_statistics`

It also publishes `pogeo://catalog` and `pogeo://conformance` resources. The Streamable HTTP transport is mounted at:

```text
http://localhost:8080/mcp
```

Example MCP configuration for a client that accepts remote HTTP servers:

```json
{
  "mcpServers": {
    "pogeo": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

The server uses the official Rust MCP SDK and its host-header protection. For non-local deployments, place PoGeo behind an authenticated reverse proxy and restrict accepted hostnames and origins.

## Safe Ollama tool loop

```text
User question
    ↓
Ollama selects a typed PoGeo tool
    ↓
PoGeo validates collection, coordinates, distance, bbox, and result limit
    ↓
PoGeo builds parameterized PostGIS queries from allowlisted identifiers
    ↓
PostGIS returns GeoJSON
    ↓
Ollama explains the verified result
    ↓
MapLibre renders the same result
```

The model never receives database credentials and cannot submit arbitrary SQL.

## Publish your own collection

The MVP uses an explicit catalog in `src/catalog.rs`. This prevents accidental exposure of private schemas. To publish a table:

1. Create a PostGIS table or view with an integer `id` and `geometry(..., 4326)` column named `geom`.
2. Add its metadata, trusted table name, properties, and searchable columns to `COLLECTIONS`.
3. Run `cargo test` and verify the API response.
4. Add row-level security or a restricted database role before exposing sensitive data.

A future release will support signed declarative catalog configuration while preserving the same allowlist guarantees.

## Development

```bash
# Start only the dependencies
docker compose up -d postgis ollama

# Pull a tool-capable model
ollama pull qwen3:4b

# Run PoGeo locally
cargo run

# Quality checks
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets --all-features
```

Important environment variables are documented in `.env.example`.

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                    PoGeo web application                  │
│             MapLibre map + Ollama spatial chat            │
└────────────────────────────┬─────────────────────────────┘
                             │ JSON
┌────────────────────────────▼─────────────────────────────┐
│                       PoGeo / Rust                        │
│  OGC-style API │ MCP tools/resources │ Ollama tool loop  │
│             shared allowlisted GeoService                 │
└────────────────────────────┬─────────────────────────────┘
                             │ parameterized SQL
┌────────────────────────────▼─────────────────────────────┐
│                    PostgreSQL + PostGIS                   │
│          spatial indexes │ GeoJSON │ distance             │
└──────────────────────────────────────────────────────────┘
```

See [the architecture notes](docs/architecture.md) for trust boundaries and extension points.

## Project status

PoGeo `0.1.0` is a functional reference implementation and foundation for a larger project. It is not yet a formally certified OGC API implementation. Production deployments should add OIDC, policy enforcement, a migration strategy, formal OGC conformance tests, rate limiting, and deployment-specific observability.

## License

Licensed under the [Apache License 2.0](LICENSE).
