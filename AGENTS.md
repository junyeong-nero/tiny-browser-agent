# Repository Guidelines

## Project Structure & Module Organization
Application code lives in `src/`. The CLI entry point is the top-level `main.py`, which configures optional logging and starts `BrowserAgent.agent_loop()`. The main agent implementation lives in `src/agents/actor_agent.py`; `agent_loop()` is the outer loop and `run_one_iteration()` handles a single model/action step. The internal LLM boundary lives under `src/llm/`, where `src/llm/client.py` owns provider selection and retries and `src/llm/provider/` contains Gemini API bootstrap code. Browser environments are organized under `src/browser/`: `PlaywrightBrowser` is in `src/browser/playwright.py` and artifact logging is in `src/browser/artifact_logger.py`. Custom tool functions live in `src/tools/`. Tests live in `tests/` and currently cover the CLI, agent behavior, the LLM layer, and Playwright logging. Project metadata and test configuration live in `pyproject.toml`; dependency locking is in `uv.lock`.

## Build, Test, and Development Commands
Use `uv` for local setup and execution.

- `uv sync --dev`: create/update `.venv` and install runtime plus test dependencies.
- `uv run pytest`: run the full test suite.
- `uv run main.py --help`: inspect available CLI flags.
- `uv run main.py "summarize this page"`: run the agent locally with the Playwright backend.
- `uv run main.py "summarize this page" --initial_url "https://example.com"`: start from a specific page.
- `uv run main.py "summarize this page" --headless True`: run Playwright headless.
- `uv run main.py "summarize this page" --log`: save Playwright history and video under `logs/history/<timestamp>/`.
- `uv run playwright install chromium`: install the browser binary required for the Playwright backend.
- `uv run playwright install-deps chromium`: install Playwright system dependencies when required by your machine.

Important CLI behavior:
- `query` is a positional argument (not a flag).
- `--log` saves Playwright video, per-step history, and `actions.jsonl`.
- `--model` overrides the default Gemini model name.

## Coding Style & Naming Conventions
Follow standard Python style with 4-space indentation, explicit imports, and repo-consistent type hints. The codebase uses `snake_case` for functions, methods, variables, and modules, and `PascalCase` for classes such as `BrowserAgent`, `PlaywrightBrowser`, and `EnvState`. Prefer small focused methods and short, direct docstrings where behavior is not obvious, especially on interfaces and lifecycle methods. Existing code relies on Pydantic models and typed signatures (`Literal`, `Optional`, typed tuples/lists), so preserve that style instead of introducing untyped helpers.

## Testing Guidelines
Run tests with `pytest`, but note that the current suite is written in `unittest` style with `unittest.mock`. Add or update tests before refactoring behavior, especially around CLI argument handling, browser abstractions, and Playwright logging behavior. Name new test files `test_*.py`; existing tests place `test_<behavior>` methods inside `unittest.TestCase` classes. Keep tests deterministic by mocking browser, model, and API clients rather than calling external services directly. Use temporary directories and patched sleeps for filesystem- or timing-sensitive behavior when possible.

## Commit & Pull Request Guidelines
Recent history uses concise, imperative commit subjects. Prefer one focused change per commit. Pull requests should describe the behavioral change, note any config or dependency updates, and link the relevant issue when applicable.

## Security & Configuration Tips
Do not hardcode secrets. Use the environment variables actually read by the code: `GEMINI_API_KEY`. Validate browser-related setup locally before opening a PR. Be careful with `--log`: it stores screenshots, DOM snapshots, metadata, action history (`actions.jsonl`), and Playwright video under `logs/history/<timestamp>/`, which can capture sensitive page content and URLs. Keep the existing Playwright launch hardening intact; the local backend intentionally does not disable the browser sandbox.
