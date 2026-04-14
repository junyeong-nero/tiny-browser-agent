# Computer Use Preview

Browser agent example for Gemini Computer Use with two browser backends:

- `playwright`: local Chromium controlled by Playwright
- `browserbase`: remote browser session via Browserbase

The CLI entry point is `main.py`. Runtime code lives in `src/`.

## Desktop Bridge Runtime

The desktop shell runs the React renderer against a stdio Python bridge instead of a local FastAPI session server.

## Electron Desktop Shell

An Electron shell scaffold now lives under `desktop/`.

Structure:

```text
desktop/
├── package.json
├── tsconfig.json
└── src/
    ├── main.ts
    ├── preload.ts
    ├── python.ts
    ├── config.ts
    ├── pythonBridgeClient.ts
    └── bridge/
        └── channels.ts
```

The current scaffold uses this flow:

- Electron `main` starts the Python desktop bridge via `uv run python main.py --desktop_bridge --headless True`
- Electron `preload` installs `window.__COMPUTER_USE_DESKTOP_BRIDGE__`
- The React renderer in `web/` consumes that bridge through the desktop bridge abstractions already added in `web/src/api/`

Current browser surface behavior:

- Electron now creates a hosted `WebContentsView` for the browser surface region
- renderer bounds/focus events are forwarded to the Electron shell through `browserSurface.setBounds()` and `browserSurface.focus()`
- the Python runtime controls that hosted surface through the Electron command bridge used by `ElectronSurfaceComputer`

Current limitation:

- browser mode in the standalone web renderer is no longer a supported runtime path unless a client is injected explicitly
- the intended runtime is the desktop shell with the installed desktop bridge

Renderer loading:

- Development: `ELECTRON_RENDERER_URL=http://127.0.0.1:5173`
- Production: `web/dist/index.html`

Desktop shell commands:

```bash
cd desktop
npm install
npm run build
npm run start
```

For local renderer development, run the web dev server separately:

```bash
cd web
npm install
npm run dev

cd ../desktop
npm install
npm run dev
```

## Requirements

- Python `>=3.12,<3.13`
- `uv`
- A Gemini API key or Vertex AI credentials
- For Browserbase: `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID`

## Quick Start

```bash
uv sync --dev
uv run playwright install chromium
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
uv run python main.py --env playwright --query "Summarize this page"
```

If Playwright needs system packages on your machine, run:

```bash
uv run playwright install-deps chromium
```

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

### OpenAI step summarizer (optional)

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export ACTION_SUMMARY_PROVIDER="openai"
export ACTION_SUMMARY_MODEL="gpt-4o-mini"
```

When enabled, the main browser agent still uses Gemini/Vertex AI for action generation.
OpenAI is used only to rewrite executed action steps into short user-facing summaries.
If `OPENAI_API_KEY` is present, the app now auto-enables the OpenAI summarizer even when `ACTION_SUMMARY_PROVIDER` is omitted.
If OpenAI fails, the app falls back to built-in summaries.

### Browserbase

```bash
export BROWSERBASE_API_KEY="YOUR_BROWSERBASE_API_KEY"
export BROWSERBASE_PROJECT_ID="YOUR_BROWSERBASE_PROJECT_ID"
```

## Usage

Basic command:

```bash
uv run python main.py --query "Go to Google and search for Gemini Computer Use"
```

### Playwright

Run locally with Playwright:

```bash
uv run python main.py \
  --env playwright \
  --query "Open Example Domain and summarize the page"
```

Start from a specific URL:

```bash
uv run python main.py \
  --env playwright \
  --initial_url "https://example.com" \
  --query "Summarize this page"
```

Run headless:

```bash
uv run python main.py \
  --env playwright \
  --headless True \
  --query "Summarize this page"
```

Show cursor highlighting for visual debugging:

```bash
uv run python main.py \
  --env playwright \
  --highlight_mouse \
  --query "Click the first link"
```

### Session Logging

Add `--log` to save Playwright execution artifacts:

```bash
uv run python main.py \
  --env playwright \
  --log \
  --query "Summarize this page"
```

This creates a timestamped directory under `logs/history/`:

```text
logs/history/<timestamp>/
├── history/
│   ├── step-0001.png
│   ├── step-0001.html
│   ├── step-0001.json
│   └── ...
└── video/
    └── <playwright-video-file>
```

- `history/*.png`: screenshot captured for each agent step
- `history/*.html`: DOM snapshot for each step
- `history/*.json`: step metadata including URL and file names
- `video/`: Playwright session recording

`--log` is only supported with `--env playwright`.

### Browserbase

Run against Browserbase:

```bash
uv run python main.py \
  --env browserbase \
  --query "Open Example Domain and summarize the page"
```

## CLI Reference

```text
usage: main.py [-h] [--query QUERY] [--desktop_bridge]
               [--env {playwright,browserbase}] [--initial_url INITIAL_URL]
               [--highlight_mouse] [--headless HEADLESS] [--log] [--model MODEL]
```

| Argument | Description | Default |
| - | - | - |
| `--query` | Natural-language instruction for the agent. Required unless `--desktop_bridge` is set. | Optional |
| `--desktop_bridge` | Run the desktop bridge over stdio instead of the CLI agent loop. | `False` |
| `--env` | Browser backend to use: `playwright` or `browserbase`. | `playwright` |
| `--initial_url` | Initial page opened before the agent starts. | `https://www.google.com` |
| `--highlight_mouse` | Highlight cursor position in Playwright screenshots. | `False` |
| `--headless` | Launch Playwright headless. Use `True` or `False`. | `False` |
| `--log` | Save Playwright video and per-step DOM/screenshot history. | `False` |
| `--model` | Model name passed to the configured LLM provider. | `gemini-2.5-computer-use-preview-10-2025` |

## Environment Variables

| Variable | Description |
| - | - |
| `GEMINI_API_KEY` | API key for the Gemini Developer API. |
| `USE_VERTEXAI` | Set to `true` or `1` to use Vertex AI instead of the Gemini Developer API. |
| `VERTEXAI_PROJECT` | Vertex AI project ID. |
| `VERTEXAI_LOCATION` | Vertex AI location. |
| `ACTION_SUMMARY_PROVIDER` | Optional action-step summarizer provider. Supports `openai` and `openrouter`. If omitted, the app infers `openai` from `OPENAI_API_KEY` or `openrouter` from `OPENROUTER_API_KEY`. |
| `ACTION_SUMMARY_MODEL` | Optional action-step summarizer model. Defaults to `gpt-4o-mini`. |
| `ACTION_SUMMARY_TIMEOUT_SECONDS` | Optional timeout for action-step summarization requests. Defaults to `15`. |
| `OPENAI_API_KEY` | OpenAI API key for direct action-step summarization. |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible base URL. Defaults to `https://api.openai.com/v1`. |
| `OPENROUTER_API_KEY` | OpenRouter API key. |
| `OPENROUTER_BASE_URL` | Optional OpenRouter-compatible base URL. Defaults to `https://openrouter.ai/api/v1`. |
| `OPENROUTER_HTTP_REFERER` | Optional `HTTP-Referer` header sent to OpenRouter. |
| `OPENROUTER_TITLE` | Optional `X-Title` header sent to OpenRouter. |
| `BROWSERBASE_API_KEY` | Browserbase API key. |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID. |

## Project Layout

- `main.py`: CLI entry point and backend selection
- `src/agent.py`: `BrowserAgent`, browser-action orchestration, `agent_loop()`, and `run_one_iteration()`
- `src/llm/client.py`: app-facing LLM client with provider selection and bounded retry handling
- `src/llm/provider/`: Gemini API and Vertex AI provider bootstrap implementations
- `src/computers/computer.py`: shared `Computer` interface and `EnvState`
- `src/computers/playwright/playwright.py`: local Playwright backend
- `src/computers/browserbase/browserbase.py`: Browserbase backend
- `tests/test_main.py`: CLI tests
- `tests/test_agent.py`: agent behavior tests
- `tests/test_playwright_logging.py`: Playwright logging tests

## Agent Pipeline

The runtime flow starts in `main.py`, selects a browser backend, initializes `BrowserAgent`, and then loops until the model stops issuing browser actions.

```mermaid
flowchart TD
    A[CLI: main.py] --> B[Parse args]
    B --> C{Select backend}
    C -->|playwright| D[PlaywrightComputer]
    C -->|browserbase| E[BrowserbaseComputer]
    D --> F[Create BrowserAgent]
    E --> F
    F --> G[Initialize LLMClient and tool config]
    G --> H[Seed contents with user query]
    H --> I[agent_loop]
    I --> J[run_one_iteration]
    J --> K[Call Gemini model]
    K --> L{Function calls returned?}
    L -->|No| M[Save final_reasoning]
    M --> N[Complete]
    L -->|Yes| O[handle_action]
    O --> P[Execute browser action via backend]
    P --> Q[Capture EnvState screenshot and url]
    Q --> R[Append FunctionResponse to contents]
    R --> S[Trim old screenshot payloads]
    S --> I
```

### Per-iteration flow

```mermaid
sequenceDiagram
    participant U as User query / contents
    participant A as BrowserAgent
    participant M as Gemini model
    participant C as Computer backend
    participant P as Browser page

    U->>A: Existing contents + query
    A->>M: generate_content(model, contents, config)
    M-->>A: reasoning + function calls

    alt no function calls
        A-->>A: Store final_reasoning
        A-->>U: COMPLETE
    else function calls present
        loop each function call
            A->>A: handle_action(function_call)
            A->>C: click / type / scroll / navigate / ...
            C->>P: Perform browser operation
            P-->>C: Updated page state
            C-->>A: EnvState(screenshot, url)
        end
        A-->>A: Append FunctionResponse to contents
        A-->>A: Remove older screenshot payloads
        A-->>U: CONTINUE
    end
```

Key responsibilities:

- `main.py`: parses CLI arguments, chooses `playwright` or `browserbase`, and starts the outer loop.
- `src/agent.py`: owns action dispatch, conversation state, and iteration control.
- `src/llm/client.py`: owns provider bootstrap, model request execution, and bounded retry handling.
- `src/computers/playwright/playwright.py`: executes local browser actions and captures screenshots/DOM history.
- `src/computers/browserbase/browserbase.py`: connects the same action model to a remote Browserbase session.

## Development

Run tests:

```bash
uv run pytest
```

Inspect CLI options:

```bash
uv run python main.py --help
```

## Security Notes

- Do not hardcode secrets; use environment variables instead.
- `--log` stores screenshots, DOM snapshots, metadata, and Playwright video under `logs/history/<timestamp>/`, which may capture sensitive content and URLs.
- UI sessions also write screenshots and HTML/JSON artifacts under `logs/history/ui/<session-id>/`, and can capture sensitive page content and URLs while a session is running.
- The local Playwright backend keeps the browser sandbox enabled.
