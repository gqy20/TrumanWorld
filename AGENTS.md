# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI service, simulation core, persistence layer, and Alembic migrations. Main application code lives under `backend/app/` with feature areas such as `api/`, `agent/`, `sim/`, `store/`, and `infra/`. Backend tests live in `backend/tests/`. `frontend/` contains the Next.js 15 director console; route files are under `frontend/app/`. `agents/` stores agent-facing configuration and prompts, while `docs/` holds product and architecture notes.

## Build, Test, and Development Commands
Use the top-level `Makefile` for common workflows:

- `make install`: install backend dependencies with `uv` and frontend dependencies with `npm`.
- `make backend-dev`: run the FastAPI server with reload on `http://127.0.0.1:8000`.
- `make frontend-dev`: start the Next.js dev server on `http://127.0.0.1:3000`.
- `make migrate`: apply Alembic migrations.
- `make lint`: run `ruff check` on backend code.
- `make format`: run `ruff format` on backend code.
- `make test`: run backend `pytest`.
- `make pre-commit`: run repository hooks before pushing.

For frontend-only checks, run `cd frontend && npm run lint` or `npm run build`.

## Coding Style & Naming Conventions
Python targets 3.12+, uses 4-space indentation, and is formatted by Ruff with a 100-character line limit. Keep backend modules `snake_case`, classes `PascalCase`, and constants `UPPER_SNAKE_CASE`. TypeScript/React code in `frontend/` uses 2-space indentation, component names in `PascalCase`, and route files following Next.js App Router conventions such as `app/page.tsx` and `app/layout.tsx`.

## Testing Guidelines
Backend tests use `pytest` with `pytest-asyncio`; name files `test_*.py` and keep test names behavior-focused, for example `test_get_agent_returns_404_when_agent_missing`. Add tests alongside backend changes, especially for API endpoints, repositories, and simulation behavior. The frontend currently has no test suite, so at minimum run `npm run lint` and `npm run build` after UI changes.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit prefixes such as `feat:`, `fix:`, `test:`, and `chore:`. Keep commit subjects imperative and scoped to one change. Pull requests should include a short summary, linked issue or task, commands run (`make test`, `make lint`, `npm run lint`), and screenshots for visible frontend changes. Note any schema, env, or migration impact explicitly.

## Security & Configuration Tips
Start from `.env.example` and keep secrets in a local `.env` only. Do not commit generated files from `.venv/`, caches, or local database state. Run `make pre-commit` before opening a PR to catch formatting, YAML/TOML, and merge-conflict issues early.
