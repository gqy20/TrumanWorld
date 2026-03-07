PYTHON ?= python3
BACKEND_DIR := backend
FRONTEND_DIR := frontend

.PHONY: install backend-install frontend-install backend-dev frontend-dev lint format test migrate pre-commit

install: backend-install frontend-install

backend-install:
	cd $(BACKEND_DIR) && uv sync --extra dev

frontend-install:
	cd $(FRONTEND_DIR) && npm install

backend-dev:
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev

lint:
	cd $(BACKEND_DIR) && uv run ruff check app tests

format:
	cd $(BACKEND_DIR) && uv run ruff format app tests

test:
	cd $(BACKEND_DIR) && uv run pytest

migrate:
	cd $(BACKEND_DIR) && uv run alembic upgrade head

pre-commit:
	$(PYTHON) -m pre_commit run --all-files
