# Repository Guidelines

## Project Structure & Module Organization
- Current repository is empty aside from `.git`. Create a top-level `src/` (or `pt_plugin_sync/`) package for Python modules, `tests/` for automated tests, and `docs/` for design notes if needed.
- Place CLI entrypoints under `src/pt_plugin_sync/cli.py` (or similar) and keep OS integration code (launchd, file watching) in separate modules.
- Store sample configs or fixtures in `tests/fixtures/`.

## Build, Test, and Development Commands
- `python -m venv .venv` sets up a local virtual environment.
- `source .venv/bin/activate` activates the environment.
- `pip install -r requirements.txt` (or `pip install -e .`) installs dependencies once a `requirements.txt` or `pyproject.toml` exists.
- `pytest` runs the test suite when tests are present.

## Coding Style & Naming Conventions
- Use 4-space indentation and follow PEP 8 naming (`snake_case` for functions, `PascalCase` for classes).
- Prefer type hints for public functions and dataclasses for config/report models.
- If you add formatters/linters, document them here (e.g., `ruff`, `black`, `mypy`) and include their config in the repo.

## Testing Guidelines
- Prefer `pytest` for unit tests with files named `test_*.py` under `tests/`.
- Keep tests focused on pure functions; mock filesystem and OS calls where needed.
- No coverage target is defined yet; establish one if the project grows.

## Commit & Pull Request Guidelines
- No commit history exists yet; use concise, imperative commit messages (e.g., `Add config loader`, `Fix launchd logging`).
- For pull requests, include a short summary, testing notes, and any relevant screenshots/logs when UI or launchd behavior changes.

## Security & Configuration Tips
- Avoid hardcoding user paths; read from config and expand `~` with `os.path.expanduser`.
- Keep secrets out of the repo; store user-specific paths in config files under `~/.config`.
