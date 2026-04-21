import argparse
import sys
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agents.actor_agent import BrowserAgent
from browser import PlaywrightBrowser


PLAYWRIGHT_SCREEN_SIZE = (1600, 900)
LOGS_DIR = Path(__file__).resolve().parent / "logs" / "history"


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected True or False.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the browser agent with a query.")
    parser.add_argument(
        "query",
        type=str,
        help="The query for the browser agent to execute.",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=("playwright",),
        default="playwright",
        help="The computer use environment to use.",
    )
    parser.add_argument(
        "--initial_url",
        type=str,
        default="https://www.google.com",
        help="The inital URL loaded for the computer.",
    )
    parser.add_argument(
        "--highlight_mouse",
        action="store_true",
        default=False,
        help="If possible, highlight the location of the mouse.",
    )
    parser.add_argument(
        "--headless",
        type=parse_bool,
        default=False,
        help="Whether to launch Playwright in headless mode. Use True or False.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        default=False,
        help="Save Playwright video and per-step DOM/screenshot history under logs/history/.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-computer-use-preview-10-2025",
        help="Set which main model to use.",
    )
    args = parser.parse_args()

    log_dir = None
    if args.log:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_dir = str(LOGS_DIR / timestamp)

    env = PlaywrightBrowser(
        screen_size=PLAYWRIGHT_SCREEN_SIZE,
        initial_url=args.initial_url,
        highlight_mouse=args.highlight_mouse,
        headless=args.headless,
        log_dir=log_dir,
    )

    with env as browser_computer:
        agent = BrowserAgent(
            browser_computer=browser_computer,
            query=args.query,
            model_name=args.model,
        )
        agent.agent_loop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
