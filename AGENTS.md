# Repository Guidelines

## Project Structure & Module Organization
Application code lives in `src/`. The main agent loop is in `src/agent.py`, and browser backends are in `src/computers/` with separate implementations for local Playwright and Browserbase. The CLI entry point is the top-level `main.py`. Tests live in `tests/` and mirror the runtime modules: `tests/test_agent.py` and `tests/test_main.py`. Project metadata and dependency locking are managed with `pyproject.toml` and `uv.lock`.

## Build, Test, and Development Commands
Use `uv` for local setup and execution.

- `uv sync --dev`: create/update `.venv` and install runtime plus test dependencies.
- `uv run pytest`: run the full test suite.
- `uv run python main.py --help`: inspect available CLI flags.
- `uv run python main.py --query "summarize this page"`: run the agent locally.
- `uv run playwright install chromium`: install the browser binary required for the Playwright backend.

## Coding Style & Naming Conventions
Follow standard Python style with 4-space indentation, clear type hints, and small focused functions. Use `snake_case` for functions, variables, and module names; use `PascalCase` for classes such as `BrowserAgent` and `PlaywrightComputer`. Keep imports explicit and prefer short, direct docstrings where behavior is not obvious. No formatter or linter is currently configured, so keep changes consistent with the surrounding file style.

## Testing Guidelines
This repository uses `pytest`. Add or update tests before refactoring behavior, especially around CLI argument handling and browser abstractions. Name new test files `test_*.py` and new test cases `test_<behavior>()`. Keep tests deterministic by mocking browser and API clients rather than calling external services directly.

## Commit & Pull Request Guidelines
Recent history uses concise, imperative commit subjects such as `Update README.md` or `Clarify available models.` Prefer one focused change per commit. Pull requests should describe the behavioral change, note any config or dependency updates, and link the relevant issue when applicable. Include screenshots only when UI or browser interaction behavior materially changes.

## Security & Configuration Tips
Do not hardcode secrets. Use environment variables such as `GEMINI_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `USE_VERTEXAI`, `VERTEXAI_PROJECT`, and `VERTEXAI_LOCATION`. Validate browser-related setup locally before opening a PR.
