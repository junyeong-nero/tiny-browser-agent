import threading
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Literal, Optional

from agent import BrowserAgent
from computers import Computer, PlaywrightComputer

from collections import Counter

from .models import (
    ChatMessage,
    SessionSnapshot,
    SessionStatus,
    StepRecord,
    VerificationGroup,
    VerificationItem,
    VerificationPayload,
)
from .serializers import (
    encode_screenshot_base64,
    make_initial_snapshot,
    serialize_step_actions,
)
ComputerFactory = Callable[..., AbstractContextManager[Computer]]
AgentFactory = Callable[..., BrowserAgent]


def build_verification_payload(
    snapshot: SessionSnapshot,
    steps: list[StepRecord],
) -> VerificationPayload:
    return VerificationPayload(
        session_id=snapshot.session_id,
        request_text=snapshot.request_text,
        run_summary=snapshot.run_summary,
        final_result_summary=snapshot.final_result_summary,
        verification_items=[item.model_copy(deep=True) for item in snapshot.verification_items],
        grouped_steps=_group_steps_for_verification(steps),
    )


def _group_steps_for_verification(steps: list[StepRecord]) -> list[VerificationGroup]:
    if not steps:
        return []

    groups: list[list[StepRecord]] = []
    current_group: list[StepRecord] = []

    for step in steps:
        previous_step = current_group[-1] if current_group else None
        if not current_group or _should_start_new_group(previous_step, step):
            if current_group:
                groups.append(current_group)
            current_group = [step]
        else:
            current_group.append(step)

    if current_group:
        groups.append(current_group)

    return [_build_verification_group(group_steps) for group_steps in groups]


def _should_start_new_group(previous_step: StepRecord | None, step: StepRecord) -> bool:
    if previous_step is None:
        return True

    if step.phase_id:
        return step.phase_id != previous_step.phase_id

    if previous_step.phase_id:
        return True

    if step.url and previous_step.url and step.url != previous_step.url:
        return True

    return _action_signature(step) != _action_signature(previous_step)


def _action_signature(step: StepRecord) -> str:
    if not step.function_calls:
        return ""
    return ",".join(call.name for call in step.function_calls)


def _build_verification_group(group_steps: list[StepRecord]) -> VerificationGroup:
    first_step = group_steps[0]
    last_step = group_steps[-1]
    label = (
        first_step.phase_label
        or first_step.user_visible_label
        or _short_url_label(first_step.url)
        or f"Step {first_step.step_id}"
    )
    return VerificationGroup(
        id=first_step.phase_id or f"group-{first_step.step_id}",
        label=label,
        summary=_build_group_summary(group_steps),
        step_ids=[step.step_id for step in group_steps],
        steps=[step.model_copy(deep=True) for step in group_steps],
        screenshot_path=last_step.screenshot_path,
        html_path=last_step.html_path,
        metadata_path=last_step.metadata_path,
        a11y_path=last_step.a11y_path,
    )


def _build_group_summary(group_steps: list[StepRecord]) -> str | None:
    base_summary = group_steps[0].phase_summary or group_steps[0].reasoning
    repeated_count = _repeated_action_count(group_steps)
    if repeated_count <= 1:
        return base_summary
    if base_summary:
        return f"{base_summary} · {repeated_count}회 반복"
    return f"{repeated_count}회 반복"


def _repeated_action_count(group_steps: list[StepRecord]) -> int:
    signatures = [signature for signature in (_action_signature(step) for step in group_steps) if signature]
    if not signatures:
        return 1
    return Counter(signatures).most_common(1)[0][1]


def _short_url_label(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("https://", "").replace("http://", "")


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
        self._pending_verification_items: dict[str, VerificationItem] = {}

        self._latest_snapshot = make_initial_snapshot(
            session_id=self.session_id,
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
            self._latest_snapshot.request_text = query
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

    def get_verification_payload(self):
        with self._lock:
            snapshot = self._latest_snapshot.model_copy(deep=True)
            steps = [step.model_copy(deep=True) for step in self._steps]
        return build_verification_payload(snapshot=snapshot, steps=steps)

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
            self._finalize_video_artifact(browser_computer)
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
                    a11y_path=None,
                    error_message=None,
                    phase_id=None,
                    phase_label=None,
                    phase_summary=None,
                    user_visible_label=None,
                    ambiguity_flag=None,
                    ambiguity_type=None,
                    ambiguity_message=None,
                    review_evidence=[],
                )
                self._steps.append(step)
                self._latest_snapshot.latest_step_id = step.step_id
            elif event_type == "reasoning_extracted":
                step = self._get_step_locked(step_id)
                if step:
                    step.reasoning = event.get("reasoning")
                self._latest_snapshot.last_reasoning = event.get("reasoning")
                if event.get("reasoning"):
                    self._latest_snapshot.run_summary = event.get("reasoning")
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
                    step.a11y_path = artifacts.get("a11y_path")
                if url:
                    self._latest_snapshot.current_url = url
                if screenshot is not None:
                    self._latest_snapshot.latest_screenshot_b64 = encode_screenshot_base64(
                        screenshot
                    )
                self._resolve_verification_items_locked()
            elif event_type == "review_metadata_extracted":
                self._apply_review_metadata_locked(step_id=step_id, payload=event)
            elif event_type == "step_complete":
                step = self._get_step_locked(step_id)
                if step:
                    step.status = event.get("status", "complete")
                self._apply_review_metadata_locked(step_id=step_id, payload=event)
                final_reasoning = event.get("final_reasoning")
                if final_reasoning:
                    self._latest_snapshot.final_reasoning = final_reasoning
                    self._latest_snapshot.run_summary = final_reasoning
                    if not self._latest_snapshot.final_result_summary:
                        self._latest_snapshot.final_result_summary = final_reasoning
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
        if role == "user" and not self._latest_snapshot.request_text:
            self._latest_snapshot.request_text = text

    def _apply_review_metadata_locked(
        self,
        step_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        step = self._get_step_locked(step_id)
        if step:
            if "phase_id" in payload:
                step.phase_id = payload.get("phase_id")
            if "phase_label" in payload:
                step.phase_label = payload.get("phase_label")
            if "phase_summary" in payload:
                step.phase_summary = payload.get("phase_summary")
            if "user_visible_label" in payload:
                step.user_visible_label = payload.get("user_visible_label")
            if "ambiguity_flag" in payload:
                step.ambiguity_flag = payload.get("ambiguity_flag")
            if "ambiguity_type" in payload:
                step.ambiguity_type = payload.get("ambiguity_type")
            if "ambiguity_message" in payload:
                step.ambiguity_message = payload.get("ambiguity_message")
            if "review_evidence" in payload:
                step.review_evidence = list(payload.get("review_evidence") or [])
            if "a11y_path" in payload:
                step.a11y_path = payload.get("a11y_path")

        run_summary = payload.get("run_summary")
        if run_summary:
            self._latest_snapshot.run_summary = run_summary

        final_result_summary = payload.get("final_result_summary")
        if final_result_summary:
            self._latest_snapshot.final_result_summary = final_result_summary

        verification_items = payload.get("verification_items")
        if verification_items:
            self._record_verification_items_locked(verification_items)
        self._resolve_verification_items_locked()

    def _record_verification_items_locked(self, items: list[dict[str, Any]]) -> None:
        for item_payload in items:
            source_step_id = item_payload.get("source_step_id")
            if source_step_id is None:
                continue
            item = VerificationItem(
                id=str(item_payload["id"]),
                message=str(item_payload["message"]),
                detail=item_payload.get("detail"),
                source_step_id=source_step_id,
                source_url=item_payload.get("source_url"),
                screenshot_path=item_payload.get("screenshot_path"),
                html_path=item_payload.get("html_path"),
                metadata_path=item_payload.get("metadata_path"),
                a11y_path=item_payload.get("a11y_path"),
                ambiguity_flag=item_payload.get("ambiguity_flag"),
                ambiguity_type=item_payload.get("ambiguity_type"),
                ambiguity_message=item_payload.get("ambiguity_message"),
                review_evidence=list(item_payload.get("review_evidence") or []),
                status=item_payload.get("status", "needs_review"),
            )
            self._pending_verification_items[item.id] = item

    def _resolve_verification_items_locked(self) -> None:
        resolved_items: list[VerificationItem] = []
        for item in self._pending_verification_items.values():
            step = self._get_step_locked(item.source_step_id)
            if step is None:
                continue
            resolved_items.append(
                item.model_copy(
                    update={
                        "source_url": step.url,
                        "screenshot_path": step.screenshot_path,
                        "html_path": step.html_path,
                        "metadata_path": step.metadata_path,
                        "a11y_path": item.a11y_path or step.a11y_path,
                        "ambiguity_flag": (
                            item.ambiguity_flag
                            if item.ambiguity_flag is not None
                            else step.ambiguity_flag
                        ),
                        "ambiguity_type": item.ambiguity_type or step.ambiguity_type,
                        "ambiguity_message": (
                            item.ambiguity_message or step.ambiguity_message
                        ),
                        "review_evidence": item.review_evidence or step.review_evidence,
                    }
                )
            )
        self._latest_snapshot.verification_items = [
            item.model_copy(deep=True) for item in resolved_items
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

    def _finalize_video_artifact(self, browser_computer: Computer | None = None) -> None:
        finalize_video = getattr(browser_computer, "finalize_video_artifact", None)
        if callable(finalize_video):
            try:
                finalize_video()
            except Exception:
                pass

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
