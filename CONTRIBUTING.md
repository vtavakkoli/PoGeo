# Contributing to PoGeo

Thank you for improving PoGeo.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make lint
make unit
```

Run the integration stack with:

```bash
docker compose up --build -d postgis pogeo
docker compose --profile test up --build --abort-on-container-exit --exit-code-from test test
```

## Pull requests

Keep changes focused, add tests for new behavior, update the changelog for user-visible changes,
and run Ruff plus the test suite. Do not add a raw SQL endpoint or bypass catalog validation.

Commit messages should be short and imperative, for example: `Add collection statistics tool`.
