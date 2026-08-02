# PoGeo architecture

## Design goals

PoGeo is a thin, safe application layer over PostGIS. It does not reimplement coordinate systems, spatial indexes, or geometry algorithms in Rust. Instead, it owns API contracts, catalog policy, request validation, AI orchestration, and operational controls.

## Trust boundaries

1. **Browser and MCP clients are untrusted.** Every collection identifier is resolved through the static allowlist.
2. **Ollama output is untrusted.** Tool names and arguments pass through the same validators used by the HTTP API.
3. **PostGIS identifiers are trusted only when compiled into the catalog.** User-provided values are passed as SQL parameters.
4. **Database access should be read-only in production.** The Compose demonstration uses a single local account for simplicity.
5. **MCP HTTP exposure requires network controls.** Keep it local by default or protect it with OIDC/API gateway policy.

## Main components

- `api`: HTTP routes and OGC-style resource shapes.
- `catalog`: explicitly published collections and trusted SQL identifiers.
- `geo`: shared spatial operations used by REST, MCP, and Ollama.
- `mcp`: official Rust MCP SDK adapter.
- `ai`: Ollama chat and typed tool-execution loop.
- `web`: embedded demonstration application.

## Planned evolution

- declarative, signed catalog configuration
- OIDC and collection-level authorization
- PostgreSQL row-level-security context propagation
- CQL2 filter AST
- vector tiles using `ST_AsMVT`
- OGC API Tiles, Maps, and Styles
- OpenTelemetry metrics and traces
- formal OGC conformance suite
- optional Redis tile/result cache
