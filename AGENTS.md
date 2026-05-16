# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI service, simulation core, persistence layer, and Alembic migrations. Main application code lives under `backend/app/` with feature areas such as `api/`, `agent/`, `sim/`, `store/`, and `infra/`. Backend tests live in `backend/tests/`. `frontend/` contains the Next.js 15 director console; route files are under `frontend/app/`. `agents/` stores agent-facing configuration and prompts, while `docs/` holds product and architecture notes.

## Build, Test, and Development Commands
Use the top-level `Makefile` for common workflows:

- `make install`: install backend dependencies with `uv` and frontend dependencies with `pnpm`.
- `make backend-dev`: run the FastAPI server with reload on `http://127.0.0.1:18080`.
- `make frontend-dev`: start the Next.js dev server on `http://127.0.0.1:13000`.
- `make migrate`: apply Alembic migrations.
- `make lint`: run `ruff check` on backend code.
- `make format`: run `ruff format` on backend code.
- `make test`: run backend `pytest`.
- `make pre-commit`: run repository hooks before pushing.

For frontend dependency and script workflows, use `npm` in `frontend/`. For frontend-only checks, run `cd frontend && npm run lint` or `npm run build`.

## Coding Style & Naming Conventions
Python targets 3.13+, uses 4-space indentation, and is formatted by Ruff with a 100-character line limit. Keep backend modules `snake_case`, classes `PascalCase`, and constants `UPPER_SNAKE_CASE`. TypeScript/React code in `frontend/` uses 2-space indentation, component names in `PascalCase`, and route files following Next.js App Router conventions such as `app/page.tsx` and `app/layout.tsx`.

## Testing Guidelines
Backend tests use `pytest` with `pytest-asyncio`; name files `test_*.py` and keep test names behavior-focused, for example `test_get_agent_returns_404_when_agent_missing`. Add tests alongside backend changes, especially for API endpoints, repositories, and simulation behavior. Frontend tests use Jest + @testing-library/react; test files live in `__tests__/` directories alongside source modules. Run `cd frontend && npm run test` after UI changes.

## Commit & Pull Request Guidelines
Use Conventional Commits for all commit messages:

```text
type(scope): concise imperative subject
```

Use common types such as `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, and `ci`. Include a short scope when it clarifies the affected area, for example `feat(api): add timeline filters`, `fix(frontend): handle empty run lists`, or `docs(repo): document commit format`. Omit the scope only when the change is truly cross-cutting, for example `chore: update dependencies`. Use `type(scope)!:` or a `BREAKING CHANGE:` footer for breaking changes. Keep each commit focused on one logical change.

Pull requests should include a short summary, linked issue or task, commands run (`make test`, `make lint`, `pnpm run lint`), and screenshots for visible frontend changes. Note any schema, env, or migration impact explicitly.

## Security & Configuration Tips
Start from `.env.example` and keep secrets in a local `.env` only. Do not commit generated files from `.venv/`, caches, or local database state. Run `make pre-commit` before opening a PR to catch formatting, YAML/TOML, and merge-conflict issues early.

## Documentation Guidelines
Use the lightweight `docs/` hierarchy instead of the old flat layout. New feature designs should go under `docs/product/` as `FEATURE_<TOPIC>.md` and be linked from `docs/README.md`. Current implementation and developer-facing notes belong in `docs/engineering/`, operational guides in `docs/operations/`, and scenario/reference material in `docs/references/`.
