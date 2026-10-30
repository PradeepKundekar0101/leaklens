BACKEND := cd backend &&
PY := $(BACKEND) uv run

.PHONY: dev dev-backend dev-frontend test lint format migrate seed-users generate load train evaluate ingest reset-demo setup

setup: migrate seed-users generate load train ingest reset-demo  ## everything from an empty database

dev:  ## backend :8000 and frontend :3000
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(PY) uvicorn app.main:app --reload --reload-dir app --port 8000

dev-frontend:
	cd frontend && pnpm dev

test:
	$(PY) pytest -q
	cd frontend && pnpm test

lint:
	$(PY) ruff check app scripts tests evaluation
	$(PY) ruff format --check app scripts tests evaluation
	cd frontend && pnpm lint && pnpm typecheck

format:
	$(PY) ruff check --fix app scripts tests evaluation
	$(PY) ruff format app scripts tests evaluation

migrate:
	$(PY) alembic upgrade head

seed-users:
	$(PY) python -m scripts.seed_users

generate:
	$(PY) python -m scripts.generate_policy_docs
	$(PY) python -m scripts.generate_data

load:
	$(PY) python -m scripts.load_data
	$(PY) python -m scripts.backfill_fingerprints

train:
	$(PY) python -m scripts.train_models

evaluate:
	$(PY) python -m scripts.evaluate

ingest:
	$(PY) python -m scripts.ingest_policy

reset-demo:
	$(PY) python -m scripts.reset_demo
