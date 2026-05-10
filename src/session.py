"""BrowserSession: keeps PlaywrightBrowser alive across multiple tasks."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from agents.actor_agent import AgentInterrupted, BrowserAgent
from agents.types import GroundingMode
from browser import ArtifactLogger, PlaywrightBrowser
import config as app_config
from ui.bridge import (
    emit,
    finish_active_task,
    is_task_interrupted,
    register_event_sink,
    start_next_task,
    task_queue,
    unregister_event_sink,
)


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
        video_enabled: bool = False,
    ) -> None:
        self._browser = browser_computer
        self._model_name = model_name
        self._logs_dir = logs_dir
        self._log_enabled = log_enabled
        self._video_enabled = video_enabled
        self._grounding: GroundingMode = grounding
        self._use_planner = use_planner
        self._conversation_memory: list[TaskMemory] = []

    def _make_artifact_logger(self) -> ArtifactLogger:
        if not self._log_enabled and not self._video_enabled:
            return ArtifactLogger()
        log_dir = self._logs_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
        return ArtifactLogger(
            log_dir=str(log_dir),
            history_enabled=self._log_enabled,
            video_enabled=self._video_enabled,
        )

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

    @staticmethod
    def _reject_ui_safety_confirmation(_safety: dict) -> Literal["TERMINATE"]:
        """Avoid blocking the UI session on a terminal stdin prompt.

        The browser agent emits a `safety_confirmation_required` event before
        calling this callback. Until the web UI has an explicit confirmation
        control, safest behavior is to stop the requested action instead of
        hanging the session thread on `input()`.
        """
        return "TERMINATE"

    def run_task(self, query: str) -> None:
        task_id = start_next_task()
        artifact_logger = self._make_artifact_logger()
        sink_registered = self._log_enabled
        execution_constraints = app_config.execution_constraints()
        if sink_registered:
            artifact_logger.record_session_meta(
                {
                    "query": query,
                    "model_name": self._model_name,
                    "grounding": self._grounding,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "use_planner": self._use_planner,
                    "video_enabled": self._video_enabled,
                    "constraints": execution_constraints.model_dump(),
                }
            )
            register_event_sink(artifact_logger.record_event)
        task_started_event = {"type": "task_started", "query": query, "task_id": task_id}
        session_id = artifact_logger.session_id()
        if session_id is not None:
            task_started_event["session_id"] = session_id
        emit(task_started_event)
        self._browser.set_artifact_logger(artifact_logger)
        conversation_context = self._format_conversation_memory()

        subgoals = None
        replan_callback = None
        if self._use_planner:
            from agents.planner_agent import PlannerAgent
            planner = PlannerAgent(query=query, event_sink=emit)
            subgoals = planner.plan()
            if is_task_interrupted():
                emit({"type": "task_interrupted", "query": query, "task_id": task_id, "reason": "Task interrupted by user."})
                finish_active_task(task_id)
                if sink_registered:
                    unregister_event_sink(artifact_logger.record_event)
                return
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
            interrupt_checker=is_task_interrupted,
            safety_confirmation_callback=self._reject_ui_safety_confirmation,
            max_steps_per_subgoal=execution_constraints.max_steps_per_subgoal,
            max_total_steps=execution_constraints.max_total_steps,
            max_subgoals=execution_constraints.max_subgoals,
        )
        try:
            try:
                result = agent.agent_loop()
            except AgentInterrupted as exc:
                self._browser.reset_to_blank()
                emit({"type": "task_interrupted", "query": query, "task_id": task_id, "reason": str(exc)})
                return
            except Exception as exc:
                emit({"type": "step_error", "step_id": -1, "error_message": str(exc)})
                self._browser.reset_to_blank()
                emit({"type": "task_failed", "query": query, "task_id": task_id, "status": "failed", "error_message": str(exc)})
                return
            if is_task_interrupted():
                self._browser.reset_to_blank()
                emit({"type": "task_interrupted", "query": query, "task_id": task_id, "reason": "Task interrupted by user."})
                return
            result_status = getattr(result, "status", "complete")
            if not isinstance(result_status, str):
                result_status = "complete"
            if result_status != "complete":
                emit({
                    "type": "task_failed",
                    "query": query,
                    "task_id": task_id,
                    "status": result_status,
                    "error_message": getattr(result, "reason", None) or getattr(result, "summary", None) or "Task did not complete successfully.",
                    "succeeded_subgoals": getattr(result, "succeeded_subgoals", 0),
                    "failed_subgoals": getattr(result, "failed_subgoals", 0),
                })
                return
            self._remember_completed_task(query, agent)
            final_reasoning = agent.final_reasoning
            if not isinstance(final_reasoning, str) or not final_reasoning.strip():
                result_summary = getattr(result, "summary", None)
                final_reasoning = result_summary if isinstance(result_summary, str) else None
            task_complete_event = {
                "type": "task_complete",
                "query": query,
                "task_id": task_id,
                "status": "complete",
            }
            if isinstance(final_reasoning, str) and final_reasoning.strip():
                task_complete_event["final_reasoning"] = final_reasoning
            emit(task_complete_event)
        finally:
            finish_active_task(task_id)
            if sink_registered:
                unregister_event_sink(artifact_logger.record_event)

    def run(self) -> None:
        """Block until the session ends (None sentinel in task_queue)."""
        emit({"type": "session_ready", "model_name": self._model_name})
        while True:
            query = task_queue.get()
            if query is None:
                break
            self.run_task(query)
        emit({"type": "session_closed"})
