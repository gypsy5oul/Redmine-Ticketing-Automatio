# Repository Guidelines

## Project Structure & Module Organization
- `backend/app` holds the FastAPI API surface, domain services, and scheduler code; shared settings live in `app/core`, and data models stay in `app/models`.
- `backend/alembic` tracks schema migrations; companion SQL seeds and backfill scripts live alongside `models/` for repeatable data setup.
- `frontend/src` contains the React + TypeScript UI split by `pages/`, reusable `components/`, hooks, and service clients; static assets and HTML shells sit in `public/`.
- Root deployment automation (`deployment/`, `deploy_now.sh`, `validate_deployment.sh`) wraps the multi-service stack defined in `docker-compose.yml`.

## Build, Test, and Development Commands
- `cd backend && pip install -r requirements.txt` prepares the FastAPI workspace (use Python 3.11 in a virtualenv).
- `cd backend && uvicorn app.main:app --reload` serves the API locally; run the APScheduler loop with `python run_scheduler.py`.
- `cd backend && pytest --cov=app` executes backend tests with coverage reporting.
- `cd frontend && npm install` to sync UI dependencies; `npm run dev` starts Vite, `npm run build` produces the production bundle, and `npm run lint` applies ESLint.
- `docker-compose up --build` launches Postgres, Redis, API workers, scheduler, and the frontend for end-to-end verification.

## Coding Style & Naming Conventions
Backend code follows PEP 8 with 4-space indentation and descriptive class names (`TicketProcessor`, `WorkloadManager`). Format Python with `black` (bundled in `requirements.txt`) and type-check modules via `mypy app`. Frontend TypeScript keeps the default Vite + ESLint rules: 2-space indentation, PascalCase components, camelCase utilities/hooks, and co-located styles in `index.css`. Protect secrets—load configuration through `.env` files or Docker overrides instead of hardcoding values.

## Testing Guidelines
Place new backend tests in `backend/tests/`, mirroring the module under test (e.g., `tests/services/test_workload_manager.py`) and leverage pytest fixtures plus `pytest-asyncio` for async flows. Maintain meaningful coverage for critical paths using `pytest --cov`. For UI changes, at minimum run `npm run lint`; when adding interactive features, supply component-level tests (e.g., React Testing Library) and document how to execute them in the PR.

## Commit & Pull Request Guidelines
This snapshot lacks Git metadata, so craft concise, imperative commit subjects (`feat: add SLA breach alerts`) and use bodies to capture reasoning, side-effects, and follow-up tasks. Reference related Redmine tickets or issue IDs in commits/PRs. PRs should summarize the change, list verification steps (tests, builds, lint), call out configuration updates (.env keys, Docker vars), and include screenshots or API samples whenever behavior shifts.

## Configuration & Security Notes
Copy `.env.example` (and `.env.docker` when containerizing) to inject secrets locally; avoid committing real credentials. Keep migrations in sync with `alembic revision --autogenerate` followed by `alembic upgrade head`, and update seed/backfill scripts under `backend/` as schemas evolve. Rotate secrets referenced in deployment scripts before promoting to production.

