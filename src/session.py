"""BrowserSession: keeps PlaywrightBrowser alive across multiple tasks."""
from datetime import datetime
from pathlib import Path

from agents.actor_agent import BrowserAgent
from agents.types import GroundingMode
from browser import ArtifactLogger, PlaywrightBrowser
from ui.bridge import emit, task_queue


class BrowserSession:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        model_name: str,
        logs_dir: Path,
        log_enabled: bool,
        grounding: GroundingMode = "vision",
        use_planner: bool = False,
    ) -> None:
        self._browser = browser_computer
        self._model_name = model_name
        self._logs_dir = logs_dir
        self._log_enabled = log_enabled
        self._grounding: GroundingMode = grounding
        self._use_planner = use_planner

    def _make_artifact_logger(self) -> ArtifactLogger:
        if not self._log_enabled:
            return ArtifactLogger()
        log_dir = self._logs_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
        return ArtifactLogger(log_dir=str(log_dir))

    def run_task(self, query: str) -> None:
        emit({"type": "task_started", "query": query})
        artifact_logger = self._make_artifact_logger()
        self._browser.set_artifact_logger(artifact_logger)

        subgoals = None
        if self._use_planner:
            from agents.planner_agent import PlannerAgent
            planner = PlannerAgent(query=query, event_sink=emit)
            subgoals = planner.plan()

        agent = BrowserAgent(
            browser_computer=self._browser,
            query=query,
            model_name=self._model_name,
            event_sink=emit,
            artifact_logger=artifact_logger,
            grounding=self._grounding,
            subgoals=subgoals,
        )
        try:
            agent.agent_loop()
        except Exception as exc:
            emit({"type": "step_error", "step_id": -1, "error_message": str(exc)})
            self._browser.reset_to_blank()
        emit({"type": "task_complete", "query": query})

    def run(self) -> None:
        """Block until the session ends (None sentinel in task_queue)."""
        emit({"type": "session_ready"})
        while True:
            query = task_queue.get()
            if query is None:
                break
            self.run_task(query)
        emit({"type": "session_closed"})
