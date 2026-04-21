# Gemini Project Context: tiny-browser-agent

This project is a browser automation agent powered by the Gemini Computer Use model. It uses Playwright to interact with web pages and provides a CLI and a web-based UI for monitoring and interaction.

## Project Overview

- **Core Technology:** Python 3.12, Gemini API (via `google-genai`), Playwright.
- **Architecture:** Planner-Actor model.
- **Package Manager:** `uv`.
- **Key Components:**
  - `BrowserAgent`: Orchestrates the interaction loop with Gemini.
  - `PlannerAgent`: Decomposes high-level queries into actionable subgoals.
  - `PlaywrightBrowser`: Manages the browser instance and captures screenshots/DOM states.
  - `BrowserToolExecutor`: Executes the tools called by the agent.
  - `UI Server`: A FastAPI-based web panel for monitoring the agent's progress in real-time.

## Building and Running

### Prerequisites
- Python 3.12
- `uv` installed
- `GEMINI_API_KEY` set in your environment

### Setup
```bash
# Install dependencies
uv sync --dev

# Install Playwright browsers
uv run playwright install chromium

# (Optional) Install system dependencies for Playwright
uv run playwright install-deps chromium
```

### Running the Agent
```bash
# Basic CLI usage
uv run main.py "Summarize this page"

# Specify initial URL and headless mode
uv run main.py "Search for Gemini CLI" --initial_url "https://www.google.com" --headless True

# Run with logging enabled (artifacts saved in logs/history/)
uv run main.py "Check the weather in Seoul" --log
```

### Running Tests
```bash
uv run pytest
```

## Development Conventions

- **Tool Definitions:** Custom tools are located in `src/tools/`. New tools should be added there and registered in `src/tools/constants.py` or through `build_browser_action_functions`.
- **Agent Logic:** 
  - `ActorAgent` handles the low-level execution loop, including tool calling and state management.
  - `PlannerAgent` uses a text-only Gemini model to generate a plan of subgoals.
- **Logging:** The `ArtifactLogger` (`src/browser/artifact_logger.py`) handles saving screenshots, DOM snapshots, and action history.
- **UI Interaction:** The UI communicates with the backend via WebSockets (`src/ui/server.py` and `src/ui/bridge.py`).

## Key Tools
The agent has access to several predefined tools for browser interaction:
- `open_web_browser`: Opens the browser to a specific URL.
- `navigate`: Navigates to a URL in the current tab.
- `click_at`: Clicks at specific (x, y) coordinates.
- `type_text_at`: Types text at coordinates or current focus.
- `scroll_document`: Scrolls the entire page.
- `search`: Performs a search (usually via a search engine).
- `wait_5_seconds`: Pauses execution.
- `go_back` / `go_forward`: Browser navigation.
- `key_combination`: Sends keyboard shortcuts.
- `drag_and_drop`: Performs drag actions.

## Directory Structure Highlights
- `src/agents/`: Actor, Planner, and Post-Summary agents.
- `src/browser/`: Playwright wrapper and logging logic.
- `src/llm/`: Client wrappers for Gemini and other providers (OpenAI, OpenRouter).
- `src/tools/`: Individual tool implementations.
- `src/ui/`: FastAPI server and HTML/JS for the dashboard.
- `logs/`: (Generated) Storage for session artifacts and history.
- `tests/`: Pytest suite for various components.
