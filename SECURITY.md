# Security policy

## Supported versions

PoGeo is currently an alpha project. Security fixes are applied to the latest release and the
`master` branch.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private security
advisory feature for this repository and include reproduction steps, affected endpoints, and the
potential impact.

## Security design

PoGeo is read-only by default and does not expose arbitrary SQL. Published schemas, tables,
columns, filters, and geometry fields are allowlisted in `config/collections.yaml`. SQL values are
parameterized, database statements have a timeout, and containers run without root privileges or
additional Linux privileges.

The Docker Compose configuration is a local demonstration. Add TLS, OIDC/OAuth, network policies,
secret management, PostgreSQL row-level security, and persistent audit logging before exposing a
production deployment.
