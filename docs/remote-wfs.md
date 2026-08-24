# Remote WFS providers

PoGeo 0.2 can expose allowlisted remote OGC Web Feature Service (WFS) collections beside PostGIS collections. The same REST, MCP, and Ollama tools are used for both providers, so the model never receives arbitrary network access.

## Example

```yaml
collections:
  - id: playgrounds
    title: Vienna playgrounds
    description: Public playgrounds from the City of Vienna Open Government Data service.
    provider: wfs
    wfs_url: https://data.wien.gv.at/daten/geo
    wfs_type_name: ogdwien:SPIELPLATZOGD
    wfs_version: 1.1.0
    wfs_srs_name: EPSG:4326
    wfs_output_format: json
    geometry_type: Geometry
    srid: 4326
    properties:
      - NAME
      - ADRESSE
      - BEZIRK
    default_limit: 100
    max_limit: 5000
```

## Safety model

- Remote URLs are administrator-configured in the catalog; the model cannot provide a URL.
- WFS URLs must be absolute HTTP(S) URLs and cannot contain embedded credentials.
- WFS type names are validated as simple `namespace:name` identifiers.
- Returned properties are reduced to the explicit `properties` allowlist.
- Exact-match filters are accepted only for allowlisted properties and string values are escaped before CQL construction.
- Every remote request is subject to collection and global result limits and a configurable timeout.
- Redirects are not followed, reducing SSRF risk from an allowlisted endpoint that attempts to redirect elsewhere.

## Spatial behavior

`query_features` maps to WFS `GetFeature` with optional BBOX and CQL exact-match filters. `find_nearest` uses a bounded WGS84 search box and ranks returned feature geometries by haversine distance. The nearest implementation is intended for interactive map discovery; high-volume analytical workloads should be synchronized to PostGIS for indexed spatial operations.

Vector tiles and direct numeric item lookup remain PostGIS-only in 0.2.

## Configuration

`POGEO_WFS_TIMEOUT_SECONDS` controls the outbound WFS request timeout and defaults to 30 seconds.

For production, prefer HTTPS endpoints, keep the property allowlist small, use conservative `max_limit` values, and place PoGeo behind standard network egress controls.
