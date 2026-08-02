# Security policy

## Supported versions

PoGeo is currently a pre-1.0 project. Security fixes are applied to the latest release and the default branch.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories for this repository. Do not open a public issue for exploitable findings.

## Security model

- No raw SQL API or MCP tool is provided.
- Collection, table, and column identifiers originate only from the reviewed catalog.
- Request values are bound as SQL parameters.
- Result count, distance, coordinates, and bounding boxes are constrained.
- The runtime container is non-root, read-only, and uses `no-new-privileges` in Compose.
- MCP should be protected by an authenticated reverse proxy outside local development.
- Production database roles should be read-only and use PostgreSQL row-level security where appropriate.
