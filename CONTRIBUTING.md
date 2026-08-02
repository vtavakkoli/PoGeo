# Contributing to PoGeo

Thank you for improving PoGeo.

## Development workflow

1. Create a focused branch.
2. Keep spatial operations typed and reusable through `GeoService`.
3. Never interpolate request values into SQL. Dynamic identifiers must come from the reviewed catalog.
4. Add tests for validation and policy behaviour.
5. Run:

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets --all-features
docker build --target runtime .
```

## Pull requests

Describe the behaviour change, security impact, API compatibility, and validation performed. Changes that expose a new table must explain why every published property is safe for API and AI access.
