# Repository Guidelines

## Project Structure & Module Organization
Application code lives in `src/`. The CLI entry point is the top-level `main.py`, which configures optional logging and starts `BrowserAgent.agent_loop()`. The main agent implementation lives in `src/agent.py`; `agent_loop()` is the outer loop and `run_one_iteration()` handles a single model/action step. The internal LLM boundary lives under `src/llm/`, where `src/llm/client.py` owns provider selection and retries and `src/llm/provider/` contains Gemini API bootstrap code. Browser environments are organized under `src/computers/`: the shared interface is in `src/computers/computer.py` and the local backend is `src/computers/playwright/playwright.py`. Tests live in `tests/` and currently cover the CLI, agent behavior, the LLM layer, and Playwright logging via `tests/test_main.py`, `tests/test_agent.py`, `tests/test_llm_client.py`, and `tests/test_playwright_logging.py`. Project metadata and test configuration live in `pyproject.toml`; dependency locking is in `uv.lock`.

## Build, Test, and Development Commands
Use `uv` for local setup and execution.

- `uv sync --dev`: create/update `.venv` and install runtime plus test dependencies.
- `uv run pytest`: run the full test suite.
- `uv run python main.py --help`: inspect available CLI flags.
- `uv run python main.py --query "summarize this page"`: run the agent locally with the Playwright backend.
- `uv run python main.py --initial_url "https://example.com" --query "summarize this page"`: start from a specific page.
- `uv run python main.py --headless True --query "summarize this page"`: run Playwright headless.
- `uv run python main.py --highlight_mouse --query "click the first link"`: highlight cursor movement for visual debugging.
- `uv run python main.py --log --query "summarize this page"`: save Playwright history and video under `logs/history/<timestamp>/`.
- `uv run playwright install chromium`: install the browser binary required for the Playwright backend.
- `uv run playwright install-deps chromium`: install Playwright system dependencies when required by your machine.

Important CLI behavior:
- `--env` only accepts `playwright`.
- `--log` saves Playwright video and per-step history.
- `--model` overrides the default Gemini model name.

## Coding Style & Naming Conventions
Follow standard Python style with 4-space indentation, explicit imports, and repo-consistent type hints. The codebase uses `snake_case` for functions, methods, variables, and modules, and `PascalCase` for classes such as `BrowserAgent`, `PlaywrightComputer`, and `EnvState`. Prefer small focused methods and short, direct docstrings where behavior is not obvious, especially on interfaces and lifecycle methods. Existing code relies on abstract base classes, Pydantic models, and typed signatures (`Literal`, `Optional`, typed tuples/lists), so preserve that style instead of introducing untyped helpers. No formatter or linter is currently configured, so match the surrounding file style closely.

## Testing Guidelines
Run tests with `pytest`, but note that the current suite is written in `unittest` style with `unittest.mock`. Add or update tests before refactoring behavior, especially around CLI argument handling, browser abstractions, and Playwright logging behavior. Name new test files `test_*.py`; existing tests place `test_<behavior>` methods inside `unittest.TestCase` classes. Keep tests deterministic by mocking browser, model, and API clients rather than calling external services directly. Use temporary directories and patched sleeps for filesystem- or timing-sensitive behavior when possible.

## Commit & Pull Request Guidelines
Recent history uses concise, imperative commit subjects such as `Update README.md` or `Clarify available models.` Prefer one focused change per commit. Pull requests should describe the behavioral change, note any config or dependency updates, and link the relevant issue when applicable. Include screenshots only when UI or browser interaction behavior materially changes.

## Security & Configuration Tips
Do not hardcode secrets. Use the environment variables actually read by the code: `GEMINI_API_KEY`. Validate browser-related setup locally before opening a PR. Be careful with `--log`: it stores screenshots, DOM snapshots, metadata, and Playwright video under `logs/history/<timestamp>/`, which can capture sensitive page content and URLs. Keep the existing Playwright launch hardening intact; the local backend intentionally does not disable the browser sandbox.
