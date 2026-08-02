# PoGeo architecture

PoGeo follows one rule: **REST, MCP, and Ollama must execute the same validated tools**.

```text
Browser / GIS client        MCP client                 Ollama
         |                      |                         |
         +---- FastAPI --------+----- FastMCP HTTP ------+
                                |
                         PoGeo Tool Registry
                                |
                     Pydantic validation + catalog
                                |
                     Parameterized SQL builder
                                |
                         PostgreSQL + PostGIS
```

## Trust boundaries

1. The catalog is an explicit allowlist of schemas, tables, geometry columns, and properties.
2. PostgreSQL identifiers only come from validated catalog entries.
3. User and model values are passed as PostgreSQL parameters.
4. Ollama receives tool schemas and result data, never database credentials.
5. PoGeo deliberately exposes no generic SQL execution tool.
6. Feature counts, query limits, database timeouts, and tile limits are enforced server-side.

## Main components

- `catalog.py`: validates publication metadata and PostgreSQL identifiers.
- `sql.py`: creates parameterized PostGIS statements.
- `geospatial.py`: converts database records into GeoJSON and vector tiles.
- `tools.py`: shared tool registry used by the AI layer.
- `mcp_server.py`: Streamable HTTP MCP tools and resources.
- `ollama.py`: bounded Ollama tool-calling loop.
- `api.py`: REST and OGC-style routes.
- `main.py`: application lifecycle, MCP mount, observability, and static UI.

## Production extensions

The demonstration is read-only. A production deployment should add OIDC/OAuth 2.1,
PostgreSQL row-level security, audit persistence, per-tenant catalogs, a Redis tile cache,
and formal OGC conformance testing before enabling write operations.
