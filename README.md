# Computer Use Preview

Browser agent example for Gemini Computer Use with two browser backends:

- `playwright`: local Chromium controlled by Playwright
- `browserbase`: remote browser session via Browserbase

The CLI entry point is [`main.py`](/Users/junyeong-nero/workspace/computer-use-preview/main.py). Runtime code lives in [`src/`](/Users/junyeong-nero/workspace/computer-use-preview/src).

## Quick Start

```bash
git clone https://github.com/junyeong-nero/computer-use-preview.git
cd computer-use-preview
uv sync --dev
uv run playwright install chromium
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
uv run python main.py --env playwright --query "Summarize this page"
```

If Playwright needs system packages on your machine, run:

```bash
uv run playwright install-deps chromium
```

## Requirements

- Python `>=3.12,<3.13`
- `uv`
- A Gemini API key, or Vertex AI credentials
- For Browserbase: `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID`

## Installation

Create the environment and install dependencies:

```bash
uv sync --dev
```

Optional legacy setup with `venv` and `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install Chromium for the Playwright backend:

```bash
uv run playwright install chromium
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

If `.venv` is already activated, you can also run:

```bash
python main.py --query "Go to Google and search for Gemini Computer Use"
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
usage: main.py [-h] --query QUERY [--env {playwright,browserbase}]
               [--initial_url INITIAL_URL] [--highlight_mouse]
               [--headless HEADLESS] [--log] [--model MODEL]
```

| Argument | Description | Default |
| - | - | - |
| `--query` | Natural-language instruction for the agent. | Required |
| `--env` | Browser backend to use: `playwright` or `browserbase`. | `playwright` |
| `--initial_url` | Initial page opened before the agent starts. | `https://www.google.com` |
| `--highlight_mouse` | Highlight cursor position in Playwright screenshots. | `False` |
| `--headless` | Launch Playwright headless. Use `True` or `False`. | `False` |
| `--log` | Save Playwright video and per-step DOM/screenshot history. | `False` |
| `--model` | Gemini model name. | `gemini-2.5-computer-use-preview-10-2025` |

## Environment Variables

| Variable | Description |
| - | - |
| `GEMINI_API_KEY` | API key for the Gemini Developer API. |
| `USE_VERTEXAI` | Set to `true` or `1` to use Vertex AI instead of the Gemini Developer API. |
| `VERTEXAI_PROJECT` | Vertex AI project ID. |
| `VERTEXAI_LOCATION` | Vertex AI location. |
| `BROWSERBASE_API_KEY` | Browserbase API key. |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID. |

## Development

Run tests:

```bash
uv run pytest
```

Inspect CLI options:

```bash
uv run python main.py --help
```

Project layout:

- [`src/agent.py`](/Users/junyeong-nero/workspace/computer-use-preview/src/agent.py): agent loop and Gemini interaction
- [`src/computers/playwright/playwright.py`](/Users/junyeong-nero/workspace/computer-use-preview/src/computers/playwright/playwright.py): local Playwright backend
- [`src/computers/browserbase/browserbase.py`](/Users/junyeong-nero/workspace/computer-use-preview/src/computers/browserbase/browserbase.py): Browserbase backend
- [`tests/`](/Users/junyeong-nero/workspace/computer-use-preview/tests): test suite

## Known Issues

### Native `<select>` elements in Playwright

On some operating systems, Playwright cannot capture native dropdown UI because it is rendered outside the DOM. That means the model may not see the visible dropdown state correctly in screenshots.

Workarounds:

1. Use `browserbase` instead of local `playwright`.
2. Inject a custom dropdown implementation such as `proxy-select` so the UI stays in the DOM.

The Browserbase backend is usually the more reliable option for sites that depend heavily on native OS-rendered controls.
