# Repository Guidelines

## Project Structure & Module Organization
- `daem0nmcp/` contains the core Python package (server, memory, rules, indexing).
- `daem0nmcp/migrations/` holds database schema migrations.
- `daem0nmcp/channels/` provides notification channel implementations.
- `tests/` is the pytest suite (`test_*.py`, `test_*` functions).
- `docs/`, `scripts/`, and `hooks/` contain documentation, utilities, and git hook templates.
- Runtime data lives under `.daem0nmcp/` (e.g., `.daem0nmcp/storage/daem0nmcp.db`); do not commit it.

## Build, Test, and Development Commands
- `pip install -e ".[dev]"` installs the package in editable mode with test deps.
- `python -m daem0nmcp.server` runs the MCP server directly.
- `python start_server.py --port 9876` starts the Windows HTTP launcher.
- `python -m daem0nmcp.cli <command>` runs CLI tasks (example: `python -m daem0nmcp.cli index`).
- `pytest tests/ -v --asyncio-mode=auto` runs the test suite.
- `ruff check daem0nmcp/ tests/` runs the CI lint step.
- `mypy daem0nmcp/ --ignore-missing-imports` runs the optional type check (CI does not fail on errors).

## Coding Style & Naming Conventions
- Use 4-space indentation and follow PEP 8 layout.
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused and add new features under `daem0nmcp/` with corresponding tests.
- Aim for lint-clean code under `ruff check`; no formatter is enforced, so match nearby style.

## Testing Guidelines
- Tests use `pytest` with `pytest-asyncio`; stick to `test_*.py` and `test_*` names.
- Reuse fixtures from `tests/conftest.py` where possible.
- Add regression tests for bug fixes and new CLI or server behavior.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (examples: `feat: add active context API`, `fix: handle missing vectors`).
- PRs should include a short summary, tests run, and any config or migration notes.
- Link relevant issues; include screenshots only if user-facing output changes.

## Configuration & Data
- Configuration is via `DAEM0NMCP_` environment variables (see `README.md` for options).
- Keep `.daem0nmcp/` and other local caches out of commits.
