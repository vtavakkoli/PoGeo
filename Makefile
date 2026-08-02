.PHONY: dev up down logs test fmt lint smoke reset

dev:
	cargo run

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f pogeo postgis ollama

test:
	cargo test --all-targets

fmt:
	cargo fmt --all

lint:
	cargo clippy --all-targets --all-features -- -D warnings

smoke:
	./scripts/smoke-test.sh

reset:
	docker compose down -v --remove-orphans
