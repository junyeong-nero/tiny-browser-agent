# Code Simplification Plan for tiny-browser-agent

## Summary
Refactor without changing behavior, public CLI flags, UI API routes, or provider/tool contracts. The main simplification targets are the largest mixed-responsibility modules: `BrowserAgent`, `PlaywrightBrowser`, `ActionReviewService`, and `BrowserToolExecutor`.

## Key Changes
- Split `BrowserAgent` internals into small private helper modules:
  - model turn parsing/retry handling
  - step event/review metadata emission
  - subgoal loop handling
  - tool-call execution orchestration
- Extract Playwright artifact/frame-capture logic from `PlaywrightBrowser` into an internal recorder/helper while keeping `PlaywrightBrowser` as the public browser facade.
- Simplify `BrowserToolExecutor.serialize_function_response()` by centralizing common response-field construction for `vision`, `text`, and `mixed` grounding modes.
- Reduce metadata dict duplication in `post_summary_agent.py` by introducing focused helper builders for action summaries, ambiguity metadata, and verification items.
- Keep all public imports and behavior backward-compatible; new modules should be internal implementation details only.

## Implementation Order
1. Add/confirm regression coverage for current behavior before refactoring:
   - actor retry/empty-turn/unsupported-tool behavior
   - tool response serialization for all grounding modes
   - action review metadata merge behavior
   - Playwright logging/artifact behavior
2. Refactor `BrowserToolExecutor` first because it is smaller and well-covered.
3. Refactor `ActionReviewService` metadata construction next.
4. Refactor `BrowserAgent` by moving cohesive private logic out, one responsibility at a time.
5. Refactor `PlaywrightBrowser` artifact/frame capture last, because it has the highest integration risk.

## Test Plan
- Run targeted tests after each stage:
  - `PYTHONPATH=src uv run pytest tests/test_tool_calling.py -q`
  - `PYTHONPATH=src uv run pytest tests/test_action_step_summarizer.py tests/test_agent.py -q`
  - `PYTHONPATH=src uv run pytest tests/test_playwright_logging.py tests/test_artifact_logger.py -q`
- Final verification:
  - `PYTHONPATH=src uv run pytest -q`
  - `PYTHONPATH=src uv run python -m compileall -q main.py src tests`

## Assumptions
- No new dependencies should be added.
- Simplification means smaller modules, less duplication, and clearer responsibility boundaries, not feature changes.
- Existing CLI, UI, browser-tool, and LLM-provider behavior must remain unchanged.
