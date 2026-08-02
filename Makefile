.PHONY: install format lint unit up up-ai down logs test clean

install:
	python -m pip install -e ".[dev]"

format:
	ruff format src tests
	ruff check --fix src tests

lint:
	ruff format --check src tests
	ruff check src tests
	python -m compileall -q src tests

unit:
	pytest -m "not integration"

up:
	docker compose up --build -d postgis pogeo

up-ai:
	docker compose --profile ai up --build -d

down:
	docker compose --profile ai --profile test down

logs:
	docker compose logs -f pogeo postgis ollama

test:
	docker compose --profile test up --build --abort-on-container-exit --exit-code-from test test

clean:
	docker compose --profile ai --profile test down -v --remove-orphans
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov reports/*.html
