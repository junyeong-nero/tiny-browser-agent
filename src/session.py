"""BrowserSession: keeps PlaywrightBrowser alive across multiple tasks."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agents.actor_agent import BrowserAgent
from agents.types import GroundingMode
from browser import ArtifactLogger, PlaywrightBrowser
from ui.bridge import emit, task_queue


MAX_CONVERSATION_MEMORY_ITEMS = 5
MAX_MEMORY_RESULT_CHARS = 800


@dataclass(frozen=True)
class TaskMemory:
    query: str
    result: str
    final_url: str | None = None


class BrowserSession:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        model_name: str,
        logs_dir: Path,
        log_enabled: bool,
        grounding: GroundingMode = "text",
        use_planner: bool = False,
    ) -> None:
        self._browser = browser_computer
        self._model_name = model_name
        self._logs_dir = logs_dir
        self._log_enabled = log_enabled
        self._grounding: GroundingMode = grounding
        self._use_planner = use_planner
        self._conversation_memory: list[TaskMemory] = []

    def _make_artifact_logger(self) -> ArtifactLogger:
        if not self._log_enabled:
            return ArtifactLogger()
        log_dir = self._logs_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
        return ArtifactLogger(log_dir=str(log_dir))

    def _format_conversation_memory(self) -> str | None:
        if not self._conversation_memory:
            return None

        lines = []
        for index, memory in enumerate(self._conversation_memory, start=1):
            lines.append(f"{index}. User task: {memory.query}")
            lines.append(f"   Result: {memory.result}")
            if memory.final_url:
                lines.append(f"   Final URL: {memory.final_url}")
        return "\n".join(lines)

    @staticmethod
    def _compact_result(result: str) -> str:
        normalized = " ".join(result.split())
        if len(normalized) <= MAX_MEMORY_RESULT_CHARS:
            return normalized
        return normalized[: MAX_MEMORY_RESULT_CHARS - 1].rstrip() + "…"

    def _remember_completed_task(self, query: str, agent: BrowserAgent) -> None:
        final_reasoning = agent.final_reasoning
        if not isinstance(final_reasoning, str) or not final_reasoning.strip():
            return

        latest_url = agent.latest_url
        self._conversation_memory.append(
            TaskMemory(
                query=query,
                result=self._compact_result(final_reasoning),
                final_url=latest_url,
            )
        )
        self._conversation_memory = self._conversation_memory[-MAX_CONVERSATION_MEMORY_ITEMS:]

    def run_task(self, query: str) -> None:
        emit({"type": "task_started", "query": query})
        artifact_logger = self._make_artifact_logger()
        self._browser.set_artifact_logger(artifact_logger)
        conversation_context = self._format_conversation_memory()

        subgoals = None
        replan_callback = None
        if self._use_planner:
            from agents.planner_agent import PlannerAgent
            planner = PlannerAgent(query=query, event_sink=emit)
            subgoals = planner.plan()
            if not subgoals:
                emit({"type": "planner_fallback", "reason": "no valid subgoals returned"})
                subgoals = None
            else:
                replan_callback = planner.replan

        agent = BrowserAgent(
            browser_computer=self._browser,
            query=query,
            model_name=self._model_name,
            event_sink=emit,
            artifact_logger=artifact_logger,
            grounding=self._grounding,
            subgoals=subgoals,
            replan_callback=replan_callback,
            conversation_context=conversation_context,
        )
        try:
            agent.agent_loop()
        except Exception as exc:
            emit({"type": "step_error", "step_id": -1, "error_message": str(exc)})
            self._browser.reset_to_blank()
            emit({"type": "task_failed", "query": query, "error_message": str(exc)})
            return
        self._remember_completed_task(query, agent)
        emit({"type": "task_complete", "query": query})

    def run(self) -> None:
        """Block until the session ends (None sentinel in task_queue)."""
        emit({"type": "session_ready", "model_name": self._model_name})
        while True:
            query = task_queue.get()
            if query is None:
                break
            self.run_task(query)
        emit({"type": "session_closed"})
