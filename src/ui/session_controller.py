import json
import os
import shutil
import subprocess
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Literal, Optional

from agent import BrowserAgent
from computers import Computer, PlaywrightComputer

from collections import Counter

from .models import (
    SessionSnapshot,
    SessionStatus,
    StepRecord,
    VerificationGroup,
    VerificationPayload,
)
from .session_state import SessionState

SESSION_IDLE_TIMEOUT_SECONDS = 15 * 60

ComputerFactory = Callable[..., AbstractContextManager[Computer]]
AgentFactory = Callable[..., BrowserAgent]


def build_verification_payload(
    snapshot: SessionSnapshot,
    steps: list[StepRecord],
) -> VerificationPayload:
    return VerificationPayload(
        session_id=snapshot.session_id,
        current_run_id=snapshot.current_run_id,
        last_completed_run_id=snapshot.last_completed_run_id,
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

    if step.run_id != previous_step.run_id:
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
    base_group_id = first_step.phase_id or f"group-{first_step.step_id}"
    group_id = (
        f"{first_step.run_id}:{base_group_id}"
        if first_step.run_id
        else base_group_id
    )
    label = (
        first_step.phase_label
        or first_step.user_visible_label
        or _short_url_label(first_step.url)
        or f"Step {first_step.step_id}"
    )
    return VerificationGroup(
        id=group_id,
        run_id=first_step.run_id,
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
        idle_timeout_seconds: float = SESSION_IDLE_TIMEOUT_SECONDS,
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
        self._idle_timeout_seconds = idle_timeout_seconds
        self._computer_factory = computer_factory
        self._agent_factory = agent_factory
        self._log_dir = self._artifacts_root / self.session_id
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._agent: Optional[BrowserAgent] = None
        self._state = SessionState(
            session_id=self.session_id,
            idle_timeout_seconds=self._idle_timeout_seconds,
        )
        self._message_queue: Queue[str] = Queue()
        self._close_requested = False
        self._interrupt_requested = False

    def start(self, query: str) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("Session is already running.")
            if self._state.snapshot.status != SessionStatus.IDLE:
                raise ValueError("Session has already been started.")
            self._close_requested = False
            self._interrupt_requested = False
            self._state.prepare_start(query)
            self._thread = threading.Thread(
                target=self._run_session,
                args=(query,),
                daemon=True,
                name=f"session-{self.session_id}",
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._close_requested = True
            if self._state.snapshot.status == SessionStatus.IDLE:
                self._state.mark_stopped()

    def interrupt(self) -> None:
        with self._lock:
            if self._state.snapshot.status != SessionStatus.RUNNING:
                raise ValueError("Session is not running.")
            self._interrupt_requested = True

    def close(self) -> None:
        self.stop()
        thread: Optional[threading.Thread]
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5.0)

    def enqueue_message(self, text: str) -> None:
        with self._lock:
            if self._state.snapshot.status not in (
                SessionStatus.RUNNING,
                SessionStatus.WAITING_FOR_INPUT,
            ):
                raise ValueError("Session is not running.")
            self._state.append_user_message(text)
            self._message_queue.put(text)

    def get_snapshot(self) -> SessionSnapshot:
        with self._lock:
            return self._state.snapshot_copy()

    def get_steps(self, after_step_id: int | None = None) -> list[StepRecord]:
        with self._lock:
            return self._state.steps_copy(after_step_id=after_step_id)

    def get_verification_payload(self):
        with self._lock:
            snapshot = self._state.snapshot_copy()
            steps = self._state.steps_copy()
        return build_verification_payload(snapshot=snapshot, steps=steps)

    def get_artifact_path(self, name: str) -> Path:
        candidate_name = Path(name).name
        if candidate_name != name:
            raise ValueError("Invalid artifact name.")

        for directory in (self._log_dir, self._log_dir / "history", self._log_dir / "video"):
            candidate = directory / candidate_name
            if candidate.exists() and candidate.is_file():
                return candidate
        raise FileNotFoundError(name)

    def _run_session(self, query: str) -> None:
        browser_computer: Computer | None = None
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

                while not self._close_requested:
                    with self._lock:
                        session_status = self._state.snapshot.status
                        expires_at = self._state.snapshot.expires_at

                    if session_status == SessionStatus.ERROR:
                        break

                    if session_status == SessionStatus.RUNNING:
                        status = "CONTINUE"
                        while (
                            status == "CONTINUE"
                            and not self._interrupt_requested
                            and not self._close_requested
                        ):
                            self._drain_message_queue(agent)
                            status = agent.run_one_iteration()

                        with self._lock:
                            if self._close_requested:
                                self._state.mark_stopped()
                            elif self._interrupt_requested:
                                self._interrupt_requested = False
                                self._state.enter_waiting_state(run_status="stopped")
                            elif self._state.snapshot.status != SessionStatus.ERROR:
                                self._state.enter_waiting_state(run_status="complete")
                                self._state.finalize_run(agent.final_reasoning)
                        continue

                    if (
                        session_status == SessionStatus.WAITING_FOR_INPUT
                        and expires_at is not None
                        and time.time() >= expires_at
                    ):
                        with self._lock:
                            self._state.mark_stopped("Session expired due to inactivity.")
                        break

                    queue_timeout = 0.1
                    if session_status == SessionStatus.WAITING_FOR_INPUT and expires_at is not None:
                        queue_timeout = max(0.0, min(queue_timeout, expires_at - time.time()))

                    try:
                        message = self._message_queue.get(timeout=queue_timeout)
                    except Empty:
                        continue

                    if self._close_requested:
                        break
                    agent.append_user_message(message)
                    with self._lock:
                        self._state.begin_run()
        except Exception as exc:
            with self._lock:
                self._state.mark_error(str(exc))
        finally:
            try:
                self._finalize_video_artifact(browser_computer)
            except Exception:
                pass
            try:
                self._write_actions_log()
            except Exception:
                pass
            try:
                self._convert_video_to_mp4()
            except Exception:
                pass
            with self._lock:
                if self._close_requested:
                    self._state.mark_stopped()
                self._agent = None

    def _drain_message_queue(self, agent: BrowserAgent) -> None:
        while True:
            try:
                message = self._message_queue.get_nowait()
            except Empty:
                return
            agent.append_user_message(message)

    def _handle_agent_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._state.handle_agent_event(event)

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

    def _write_actions_log(self) -> None:
        if not self._log_dir.exists():
            return
        with self._lock:
            snapshot = self._state.snapshot_copy()
            steps = self._state.steps_copy()

        payload = {
            "session_id": self.session_id,
            "exported_at": time.time(),
            "request_text": snapshot.request_text,
            "status": snapshot.status,
            "final_reasoning": snapshot.final_reasoning,
            "final_result_summary": snapshot.final_result_summary,
            "run_summary": snapshot.run_summary,
            "messages": [message.model_dump(mode="json") for message in snapshot.messages],
            "steps": [step.model_dump(mode="json") for step in steps],
        }
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            actions_path = self._log_dir / "actions.json"
            actions_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _convert_video_to_mp4(self) -> None:
        video_dir = self._log_dir / "video"
        source = video_dir / "session.webm"
        if not source.exists():
            return
        target = video_dir / "session.mp4"
        if target.exists():
            return

        ffmpeg_command = os.getenv("ELECTRON_FFMPEG_COMMAND") or shutil.which("ffmpeg")
        if not ffmpeg_command:
            return

        command = [
            ffmpeg_command,
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return
