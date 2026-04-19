# Computer Use Preview

Browser agent for Gemini Computer Use. Runs as a CLI or an Electron desktop shell.

Backends:

- `playwright`: local Chromium
- `browserbase`: remote Browserbase session
- `electron_surface`: hosted `WebContentsView` in the desktop shell

## Requirements

- Python `>=3.12,<3.13`
- `uv`
- Gemini API key or Vertex AI credentials
- Browserbase: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`

## Quick Start

```bash
uv sync --dev
uv run playwright install chromium
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
uv run python main.py --env playwright --query "Summarize this page"
```

If Playwright needs system packages:

```bash
uv run playwright install-deps chromium
```

## Desktop Shell

Electron shell under `desktop/` runs the React renderer against a stdio Python bridge.

- `main` starts the bridge via `uv run python main.py --desktop_bridge --headless True`
- `preload` installs `window.__COMPUTER_USE_DESKTOP_BRIDGE__`
- Electron hosts a `WebContentsView` as the browser surface; the renderer forwards bounds/focus through `browserSurface.setBounds()` / `browserSurface.focus()`
- The Python runtime drives that surface through `ElectronSurfaceComputer`

Renderer loading:

- Dev: `ELECTRON_RENDERER_URL=http://127.0.0.1:5173`
- Prod: `web/dist/index.html`

Run:

```bash
cd desktop
npm install
npm run build
npm run start
```

Dev (renderer + shell):

```bash
cd web && npm install && npm run dev
cd ../desktop && npm install && npm run dev
```

Note: browser mode in the standalone web renderer is not a supported runtime path unless a client is injected explicitly.

## Configuration

### Gemini Developer API

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

### Vertex AI

```bash
export USE_VERTEXAI=true
export VERTEXAI_PROJECT="YOUR_PROJECT_ID"
export VERTEXAI_LOCATION="YOUR_LOCATION"
```

### Action-step summarizer (optional)

Gemini/Vertex still drives actions; the summarizer only rewrites executed steps into short user-facing text. Auto-enables from `OPENAI_API_KEY` or `OPENROUTER_API_KEY`; falls back to built-in summaries on failure.

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export ACTION_SUMMARY_MODEL="gpt-4o-mini"  # optional
```

### Browserbase

```bash
export BROWSERBASE_API_KEY="YOUR_BROWSERBASE_API_KEY"
export BROWSERBASE_PROJECT_ID="YOUR_BROWSERBASE_PROJECT_ID"
```

## Usage

```bash
uv run python main.py --env playwright --query "Open Example Domain and summarize the page"
uv run python main.py --env playwright --initial_url "https://example.com" --query "Summarize this page"
uv run python main.py --env playwright --headless True --query "Summarize this page"
uv run python main.py --env playwright --highlight_mouse --query "Click the first link"
uv run python main.py --env browserbase --query "Open Example Domain and summarize the page"
```

### Session logging

`--log` (Playwright only) writes artifacts under `logs/history/<timestamp>/`:

```text
history/step-*.png   # screenshot per step
history/step-*.html  # DOM snapshot
history/step-*.json  # step metadata
video/               # Playwright recording
```

## CLI Reference

| Argument | Description | Default |
| - | - | - |
| `--query` | Agent instruction. Required unless `--desktop_bridge`. | — |
| `--desktop_bridge` | Run the stdio desktop bridge. | `False` |
| `--env` | `playwright` or `browserbase`. | `playwright` |
| `--initial_url` | Starting page. | `https://www.google.com` |
| `--highlight_mouse` | Highlight cursor in screenshots. | `False` |
| `--headless` | Launch Playwright headless. | `False` |
| `--log` | Save Playwright video + per-step history. | `False` |
| `--model` | LLM model name. | `gemini-2.5-computer-use-preview-10-2025` |

## Environment Variables

| Variable | Description |
| - | - |
| `GEMINI_API_KEY` | Gemini Developer API key. |
| `USE_VERTEXAI` | `true`/`1` to use Vertex AI. |
| `VERTEXAI_PROJECT` / `VERTEXAI_LOCATION` | Vertex AI project / location. |
| `ACTION_SUMMARY_PROVIDER` | `openai` or `openrouter`. Inferred from the matching API key if omitted. |
| `ACTION_SUMMARY_MODEL` | Summarizer model (default `gpt-4o-mini`). |
| `ACTION_SUMMARY_TIMEOUT_SECONDS` | Summarizer timeout (default `15`). |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI key and optional base URL. |
| `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | OpenRouter key and optional base URL. |
| `OPENROUTER_HTTP_REFERER` / `OPENROUTER_TITLE` | Optional OpenRouter headers. |
| `BROWSERBASE_API_KEY` / `BROWSERBASE_PROJECT_ID` | Browserbase credentials. |

## Project Layout

- `main.py` — CLI entry point and backend selection
- `src/agent.py` — `BrowserAgent`, `agent_loop()`, `run_one_iteration()`
- `src/llm/` — LLM client, provider bootstrap, retry
- `src/computers/computer.py` — `Computer` interface and `EnvState`
- `src/computers/playwright/playwright.py` — Playwright backend
- `src/computers/browserbase/browserbase.py` — Browserbase backend
- `src/computers/electron_surface.py` — Electron hosted-surface backend
- `src/browser_actions.py` — custom actions registered alongside Computer Use
- `tests/` — pytest suite

## Agent Pipeline

`main.py` selects a backend, builds a `BrowserAgent`, and loops until the model stops issuing actions.

```mermaid
flowchart TD
    A[main.py] --> B{Backend}
    B -->|playwright| D[PlaywrightComputer]
    B -->|browserbase| E[BrowserbaseComputer]
    D --> F[BrowserAgent]
    E --> F
    F --> G[agent_loop]
    G --> H[run_one_iteration]
    H --> I[Call Gemini]
    I --> J{Function calls?}
    J -->|No| K[Save final_reasoning → done]
    J -->|Yes| L[handle_action → backend]
    L --> M[Capture EnvState]
    M --> N[Append FunctionResponse, trim old screenshots]
    N --> G
```

## Action Spaces

Coordinates `x`, `y` are normalized to `0-1000` and rescaled to the backend's `screen_size()`.

### Predefined (`src/computers/computer.py`)

| Action | Arguments | Description |
| - | - | - |
| `open_web_browser` | — | Opens the browser. |
| `click_at` | `x`, `y` | Click at a coordinate. |
| `hover_at` | `x`, `y` | Hover at a coordinate. |
| `type_text_at` | `x`, `y`, `text`, `press_enter`, `clear_before_typing` | Type text; optionally press Enter / clear first. |
| `scroll_document` | `direction` | Scroll the page. |
| `scroll_at` | `x`, `y`, `direction`, `magnitude` | Scroll a region. |
| `wait_5_seconds` | — | Wait 5s. |
| `go_back` / `go_forward` | — | History navigation. |
| `search` | — | Jump to a search home page. |
| `navigate` | `url` | Navigate to URL. |
| `key_combination` | `keys` | E.g. `control+c`. |
| `drag_and_drop` | `x`, `y`, `destination_x`, `destination_y` | Drag source → destination. |
| `current_state` | — | Return `EnvState`. |

### Custom (`src/browser_actions.py`)

| Action | Arguments | Description |
| - | - | - |
| `press_key` | `key` | Press a single key (no modifiers). |
| `reload_page` | — | Reload current page. |
| `get_accessibility_tree` | — | Serialized a11y tree; no screenshot. |
| `upload_file` | `x`, `y`, `path` | Upload a local file to an `<input type="file">`. |

## Development

```bash
uv run pytest
uv run python main.py --help
```

## Security Notes

- Use env vars for secrets; do not hardcode.
- `--log` and UI sessions write screenshots, DOM snapshots, and video under `logs/history/` — they may capture sensitive content and URLs.
- The Playwright backend keeps the browser sandbox enabled.
