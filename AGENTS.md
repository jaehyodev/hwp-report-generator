# Repository Guidelines

## Project Structure & Module Organization
Backend services live in `backend/app`, where routers handle REST endpoints, `models/` defines ORM schemas, and `utils/` wraps Claude/HWP helpers. Test code sits in `backend/tests`, mirroring the `test_*.py` pattern defined in `pytest.ini`. Legacy HTML templates, report shells, and static assets are under `backend/templates`, `templates/`, and `static/`. The Vite + React 18 client is in `frontend/` (source beneath `frontend/src`), while sharable constants and type definitions for both runtimes are collected in `shared/`.

## Build, Test, and Development Commands
```bash
uv pip install -r backend/requirements.txt      # backend runtime dependencies
uv run uvicorn app.main:app --reload --port 8000 # FastAPI dev server
uv run pytest                                   # backend unit + integration suite
cd frontend && npm install                      # install React toolchain
npm run dev | npm run build                     # Vite dev server / production build
npm run lint                                    # ESLint pass for TS/JS code
```

## Coding Style & Naming Conventions
Python code follows PEP 8 with 4-space indents, f-string interpolation, and mandatory type hints for public functions. Format and lint before pushing: `uv run black backend app shared` and `uv run flake8 backend app`. Run `uv run mypy backend/app` for type safety on request/response models. React/TS files use ES modules, PascalCase component names (`ReportList.tsx`), and camelCase hooks/utilities. Centralize strings and enums in `shared/constants.py|ts` to keep backend and frontend synchronized.

## Testing Guidelines
Pytest automatically discovers files under `backend/tests` and enforces coverage via the `--cov=app` flag; keep the generated `coverage.xml` current for CI consumers. Use markers (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.) already declared in `pytest.ini` so selective runs like `uv run pytest -m "unit and not slow"` remain meaningful.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commits (`feat:`, `fix:`, `doc:`), so continue using lowercase type prefixes plus a short imperative summary (e.g., `feat: add jwt rotation job`). Each PR should include: concise description, linked backlog issue if applicable, screenshots or sample payloads for UI/API tweaks, and a checklist confirming `uv run pytest` and `npm run lint` pass. Keep scope focused—split backend and frontend concerns when possible.

## Security & Configuration Tips
Secrets such as `CLAUDE_API_KEY`, JWT keys, and admin bootstrap credentials belong only in `backend/.env`; never commit this file. Generated SQLite files in `backend/data/` and HWP exports in `backend/output/` should remain ignored—purge sensitive artifacts before pushing. Note every environment-variable change in `README.md` or the onboarding guides.
