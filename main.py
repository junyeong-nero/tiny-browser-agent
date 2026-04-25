import argparse
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agents.actor_agent import BrowserAgent
from agents.planner_agent import PlannerAgent
from agents.types import GroundingMode
from browser import ArtifactLogger, PlaywrightBrowser
import config as app_config


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
        nargs="?",
        default=None,
        help="The query for the browser agent to execute (omit when using --ui).",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        default=False,
        help="Start the web control panel at http://127.0.0.1:8765.",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=("playwright",),
        default="playwright",
        help="The browser environment to use.",
    )
    parser.add_argument(
        "--initial_url",
        type=str,
        default="https://www.duckduckgo.com",
        help="The initial URL loaded in the browser.",
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
        default=app_config.actor_model(),
        help="Set which main model to use.",
    )
    parser.add_argument(
        "--grounding",
        choices=["vision", "text", "mixed"],
        default="text",
        help=(
            "Page grounding mode: vision (screenshot+coords), "
            "text (ARIA snapshot+refs), or mixed (both). "
            "Note: 'text' mode requires a standard function-calling model, not computer-use."
        ),
    )
    parser.add_argument(
        "--planner",
        action="store_true",
        default=False,
        help="Use PlannerAgent to decompose the query into subgoals before execution.",
    )
    args = parser.parse_args()

    if args.ui and args.query:
        parser.error("--ui and a positional query are mutually exclusive.")
    if not args.ui and not args.query:
        parser.error("A query is required when --ui is not used.")

    artifact_logger = ArtifactLogger(
        log_dir=str(LOGS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")) if args.log else None
    )

    env = PlaywrightBrowser(
        screen_size=PLAYWRIGHT_SCREEN_SIZE,
        initial_url=args.initial_url,
        highlight_mouse=args.highlight_mouse,
        headless=args.headless,
        artifact_logger=artifact_logger,
    )

    with env as browser_computer:
        if args.ui:
            _run_ui_mode(browser_computer, args)
        else:
            subgoals = None
            replan_callback = None
            if args.planner:
                planner = PlannerAgent(
                    query=args.query,
                )
                subgoals = planner.plan()
                replan_callback = planner.replan
                print(f"Planner created {len(subgoals)} subgoal(s):")
                for sg in subgoals:
                    print(f"  [{sg.id}] {sg.description}")

            grounding: GroundingMode = args.grounding
            agent = BrowserAgent(
                browser_computer=browser_computer,
                query=args.query,
                model_name=args.model,
                artifact_logger=artifact_logger,
                grounding=grounding,
                subgoals=subgoals,
                replan_callback=replan_callback,
            )
            agent.agent_loop()
    return 0


def _run_ui_mode(browser_computer: PlaywrightBrowser, args) -> None:
    from session import BrowserSession
    import ui.server as _ui_server

    ready = threading.Event()
    server_thread = threading.Thread(target=_ui_server.start, kwargs={"on_ready": ready}, daemon=True, name="ui-server")
    server_thread.start()

    if not ready.wait(timeout=10):
        print("Warning: UI server did not start in time.")

    url = f"http://{_ui_server.HOST}:{_ui_server.port}"
    print(f"Panel: {url}")
    webbrowser.open(url)

    session = BrowserSession(
        browser_computer=browser_computer,
        model_name=args.model,
        logs_dir=LOGS_DIR,
        log_enabled=args.log,
        grounding=args.grounding,
        use_planner=args.planner,
    )
    session.run()

if __name__ == "__main__":
    raise SystemExit(main())
