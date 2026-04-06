import threading
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Literal, Optional

from agent import BrowserAgent
from computers import Computer, PlaywrightComputer

from .models import ChatMessage, SessionSnapshot, SessionStatus, StepRecord
from .serializers import (
    encode_screenshot_base64,
    make_initial_snapshot,
    serialize_step_actions,
)


ComputerFactory = Callable[..., AbstractContextManager[Computer]]
AgentFactory = Callable[..., BrowserAgent]


class SessionController:
    def __init__(
        self,
        session_id: str,
        model_name: str,
        screen_size: tuple[int, int],
        initial_url: str,
        highlight_mouse: bool,
        headless: bool,
        artifacts_root: Path,
        computer_factory: ComputerFactory = PlaywrightComputer,
        agent_factory: AgentFactory = BrowserAgent,
    ):
        self.session_id = session_id
        self._model_name = model_name
        self._screen_size = screen_size
        self._initial_url = initial_url
        self._highlight_mouse = highlight_mouse
        self._headless = headless
        self._artifacts_root = artifacts_root
        self._computer_factory = computer_factory
        self._agent_factory = agent_factory
        self._log_dir = self._artifacts_root / self.session_id
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._agent: Optional[BrowserAgent] = None
        self._steps: list[StepRecord] = []
        self._messages: list[ChatMessage] = []
        self._message_queue: Queue[str] = Queue()
        self._stop_requested = False
        self._assistant_message_emitted = False

        artifacts_base_url = f"/api/sessions/{self.session_id}/artifacts"
        self._latest_snapshot = make_initial_snapshot(
            session_id=self.session_id,
            artifacts_base_url=artifacts_base_url,
        )

    def start(self, query: str) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("Session is already running.")
            if self._latest_snapshot.status != SessionStatus.IDLE:
                raise ValueError("Session has already been started.")
            self._stop_requested = False
            self._assistant_message_emitted = False
            self._append_message_locked(role="user", text=query)
            self._latest_snapshot.status = SessionStatus.RUNNING
            self._touch_snapshot_locked()
            self._thread = threading.Thread(
                target=self._run_agent,
                args=(query,),
                daemon=True,
                name=f"session-{self.session_id}",
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_requested = True
            if self._latest_snapshot.status == SessionStatus.IDLE:
                self._latest_snapshot.status = SessionStatus.STOPPED
                self._touch_snapshot_locked()

    def enqueue_message(self, text: str) -> None:
        with self._lock:
            if self._latest_snapshot.status != SessionStatus.RUNNING:
                raise ValueError("Session is not running.")
            self._append_message_locked(role="user", text=text)
            self._message_queue.put(text)

    def get_snapshot(self) -> SessionSnapshot:
        with self._lock:
            return self._latest_snapshot.model_copy(deep=True)

    def get_steps(self, after_step_id: int | None = None) -> list[StepRecord]:
        with self._lock:
            if after_step_id is None:
                steps = self._steps
            else:
                steps = [step for step in self._steps if step.step_id > after_step_id]
            return [step.model_copy(deep=True) for step in steps]

    def get_artifact_path(self, name: str) -> Path:
        candidate_name = Path(name).name
        if candidate_name != name:
            raise ValueError("Invalid artifact name.")

        for directory in (self._log_dir / "history", self._log_dir / "video"):
            candidate = directory / candidate_name
            if candidate.exists() and candidate.is_file():
                return candidate
        raise FileNotFoundError(name)

    def _run_agent(self, query: str) -> None:
        try:
            with self._computer_factory(
                screen_size=self._screen_size,
                initial_url=self._initial_url,
                highlight_mouse=self._highlight_mouse,
                headless=self._headless,
                log_dir=str(self._log_dir),
            ) as browser_computer:
                agent = self._agent_factory(
                    browser_computer=browser_computer,
                    query=query,
                    model_name=self._model_name,
                    event_sink=self._handle_agent_event,
                )
                with self._lock:
                    self._agent = agent

                status = "CONTINUE"
                while status == "CONTINUE" and not self._stop_requested:
                    self._drain_message_queue(agent)
                    status = agent.run_one_iteration()

                with self._lock:
                    if self._stop_requested:
                        self._latest_snapshot.status = SessionStatus.STOPPED
                    elif self._latest_snapshot.status != SessionStatus.ERROR:
                        self._latest_snapshot.status = SessionStatus.COMPLETE
                        if agent.final_reasoning and not self._latest_snapshot.final_reasoning:
                            self._latest_snapshot.final_reasoning = agent.final_reasoning
                        if agent.final_reasoning and not self._assistant_message_emitted:
                            self._append_message_locked(
                                role="assistant",
                                text=agent.final_reasoning,
                            )
                            self._assistant_message_emitted = True
                    self._touch_snapshot_locked()
            self._finalize_video_artifact()
        except Exception as exc:
            with self._lock:
                self._latest_snapshot.status = SessionStatus.ERROR
                self._latest_snapshot.error_message = str(exc)
                self._touch_snapshot_locked()
        finally:
            with self._lock:
                self._agent = None

    def _drain_message_queue(self, agent: BrowserAgent) -> None:
        while True:
            try:
                message = self._message_queue.get_nowait()
            except Empty:
                return
            agent.append_user_message(message)

    def _handle_agent_event(self, event: dict[str, Any]) -> None:
        event_type = event["type"]
        step_id = event.get("step_id")
        with self._lock:
            if event_type == "step_started":
                if not isinstance(step_id, int):
                    return
                step = StepRecord(
                    step_id=step_id,
                    timestamp=event["timestamp"],
                    reasoning=None,
                    function_calls=[],
                    url=self._latest_snapshot.current_url,
                    status="running",
                    screenshot_path=None,
                    html_path=None,
                    metadata_path=None,
                    error_message=None,
                )
                self._steps.append(step)
                self._latest_snapshot.latest_step_id = step.step_id
            elif event_type == "reasoning_extracted":
                step = self._get_step_locked(step_id)
                if step:
                    step.reasoning = event.get("reasoning")
                self._latest_snapshot.last_reasoning = event.get("reasoning")
            elif event_type == "function_calls_extracted":
                step = self._get_step_locked(step_id)
                serialized_actions = serialize_step_actions(event.get("function_calls", []))
                if step:
                    step.function_calls = serialized_actions
                self._latest_snapshot.last_actions = serialized_actions
            elif event_type == "action_executed":
                step = self._get_step_locked(step_id)
                env_state = event.get("env_state") or {}
                artifacts = event.get("artifacts") or {}
                url = env_state.get("url")
                screenshot = env_state.get("screenshot")
                if step:
                    step.url = url or step.url
                    step.screenshot_path = artifacts.get("screenshot_path")
                    step.html_path = artifacts.get("html_path")
                    step.metadata_path = artifacts.get("metadata_path")
                if url:
                    self._latest_snapshot.current_url = url
                if screenshot is not None:
                    self._latest_snapshot.latest_screenshot_b64 = encode_screenshot_base64(
                        screenshot
                    )
            elif event_type == "step_complete":
                step = self._get_step_locked(step_id)
                if step:
                    step.status = event.get("status", "complete")
                final_reasoning = event.get("final_reasoning")
                if final_reasoning:
                    self._latest_snapshot.final_reasoning = final_reasoning
                    if not self._assistant_message_emitted:
                        self._append_message_locked(role="assistant", text=final_reasoning)
                        self._assistant_message_emitted = True
            elif event_type == "step_error":
                step = self._get_step_locked(step_id)
                if step:
                    step.status = "error"
                    step.error_message = event.get("error_message")
                self._latest_snapshot.status = SessionStatus.ERROR
                self._latest_snapshot.error_message = event.get("error_message")
            self._touch_snapshot_locked()

    def _append_message_locked(
        self,
        role: Literal["user", "assistant", "system"],
        text: str,
    ) -> None:
        message = ChatMessage(
            id=uuid.uuid4().hex,
            role=role,
            text=text,
            timestamp=time.time(),
        )
        self._messages.append(message)
        self._latest_snapshot.messages = [
            existing_message.model_copy(deep=True) for existing_message in self._messages
        ]

    def _get_step_locked(self, step_id: int | None) -> StepRecord | None:
        if step_id is None:
            return None
        for step in reversed(self._steps):
            if step.step_id == step_id:
                return step
        return None

    def _touch_snapshot_locked(self) -> None:
        self._latest_snapshot.updated_at = time.time()

    def _finalize_video_artifact(self) -> None:
        video_dir = self._log_dir / "video"
        if not video_dir.exists():
            return
        session_video_path = video_dir / "session.webm"
        if session_video_path.exists():
            return
        candidates = sorted(video_dir.glob("*.webm"))
        if not candidates:
            return
        candidates[0].replace(session_video_path)
