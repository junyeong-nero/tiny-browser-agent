# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Python `>=3.12,<3.13`, managed via `uv` (see `pyproject.toml`, `uv.lock`).
- `pyproject.toml` sets `pythonpath = ["src", "."]` for pytest; `main.py` also inserts `src/` onto `sys.path`, so imports inside `src/` are written as top-level (`from agents...`, `from llm...`) — don't rewrite them to `src....`.
- Requires `GEMINI_API_KEY`. Optional: `OPENAI_API_KEY` / `OPENROUTER_API_KEY` (+ base URLs) for the action-step summarizer, `ACTION_SUMMARY_PROVIDER`/`ACTION_SUMMARY_MODEL`/`ACTION_SUMMARY_TIMEOUT_SECONDS`, `COMPUTER_USE_FFMPEG_COMMAND`.

## Common commands

```bash
uv sync --dev                         # create .venv, install runtime + dev deps
uv run playwright install chromium    # one-time browser binary install
uv run playwright install-deps chromium  # system libs if needed

uv run pytest                         # run full test suite
uv run pytest tests/test_agent.py     # single file
uv run pytest tests/test_agent.py::TestBrowserAgent::test_xxx  # single test

uv run main.py "query"                # run CLI agent
uv run main.py --ui                   # start FastAPI/uvicorn control panel at :8765
uv run main.py "query" --planner --grounding mixed --log --headless True
uv run main.py --help
```

Tests are `unittest.TestCase`-style but invoked through pytest. Mock the browser, LLM client, and API calls — do not hit real services.

## Model configuration

`config.yaml` at repo root defines model names consumed by `src/config.py`:

```yaml
models:
  actor:    # computer-use model (BrowserAgent)
  planner:  # text model (PlannerAgent)
  summary:  # summarizer model
```

`--model` CLI flag overrides `actor`. The planner and summary models are read from `config.yaml` only.

## Architecture

Entry point `main.py` has two modes:

1. **CLI** (`uv run main.py "query"`) — constructs `PlaywrightBrowser`, optionally runs `PlannerAgent` to produce `Subgoal`s, then drives a single `BrowserAgent.agent_loop()`.
2. **UI** (`--ui`) — spawns a FastAPI/uvicorn server (`src/ui/server.py`) in a daemon thread, opens the panel, and a long-lived `BrowserSession` (`src/session.py`) reuses one `PlaywrightBrowser` across multiple user tasks via `ui.bridge.task_queue`/`emit`.

### Agent layer (`src/agents/`)

- `actor_agent.py::BrowserAgent` — the core loop. `agent_loop()` iterates `run_one_iteration()`: send history to the model, receive function calls, execute via `BrowserToolExecutor`, append `FunctionResponse` parts, and trim old screenshots (`MAX_RECENT_TURN_WITH_SCREENSHOTS`) / ARIA snapshots from the context window.
- `planner_agent.py::PlannerAgent` — optional query decomposition into `Subgoal`s. Uses a **text** LLM (`LLMClient.for_text()`), not computer-use.
- `post_summary_agent.py` — post-step action summaries, ambiguity detection, metadata writing.
- `types.py` — `GroundingMode = Literal["vision", "text", "mixed"]`, `Subgoal`.

**Grounding modes** (important provider coupling):
- `vision` / `mixed` → requires `gemini_computer_use` provider.
- `text` → requires `gemini_text` provider (standard function-calling model). Attempting the wrong pairing raises `ValueError` in `BrowserAgent.__init__`.

### LLM layer (`src/llm/`)

- `client.py::LLMClient` — retry wrapper around a `BaseProvider`. Use the factory matching the agent:
  - `LLMClient.for_computer_use()` — actor with vision/mixed grounding.
  - `LLMClient.for_text()` — planner, summarizer, or actor with text grounding.
  - `LLMClient.from_env()` — generic Gemini API.
- `provider/` — `gemini_computer_use.py`, `gemini_text.py`, `gemini_api.py`, plus `openai.py` / `openrouter.py` used by the summarizer. All implement `BaseProvider` (`build_function_declaration`, `generate_content`, `sdk_client`, `name`).

### Browser layer (`src/browser/`)

- `playwright.py::PlaywrightBrowser` — context manager that owns the Playwright lifecycle; yields itself as `browser_computer`. In UI mode the same instance is reused across tasks (`reset_to_blank`, `set_artifact_logger`).
- `actions.py::build_browser_action_functions` — exposes the tool set; `EnvState` is the return type for built-in computer-use actions.
- `aria_snapshot.py` — produces ARIA snapshots and `ref`s for text-grounding tools.
- `artifact_logger.py::ArtifactLogger` — when `--log`, writes `actions.jsonl`, `history/step-*.{png,html,json}`, and Playwright video under `logs/history/<timestamp>/`.

### Tools (`src/tools/` + `src/tool_executor.py`)

Each tool is its own module (`click_at`, `click_by_ref`, `navigate`, `scroll_*`, `type_by_ref`, `type_text_at`, etc.). Vision-mode tools take pixel coords; text-mode tools (`*_by_ref`, `text_mode_tools.py`) take ARIA refs. `BrowserToolExecutor` dispatches function calls, serializes results to `FunctionResponse` parts, and `prune_old_screenshot_parts` / `prune_old_aria_parts` keep context bounded.

## Conventions specific to this repo

- Type hints are required and heavily used (Pydantic models, `Literal`, `Optional`, typed tuples). Preserve them.
- `query` on the CLI is **positional**, not `--query`.
- When adding a new tool: create `src/tools/<name>.py`, register it in `src/browser/actions.py` (`build_browser_action_functions`), and return either `EnvState` (for built-in computer-use semantics) or a `dict`/`ToolResult`.
- When adding a new provider: implement `BaseProvider` in `src/llm/provider/` and wire it via an `LLMClient.for_*` classmethod — do not bypass the retry wrapper.
- Import paths inside `src/` are flat (`from agents.actor_agent import ...`), not `src.agents...`.
