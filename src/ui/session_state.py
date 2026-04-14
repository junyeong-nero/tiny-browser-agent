import time
import uuid
from typing import Any, Literal

from .models import (
    ChatMessage,
    SessionSnapshot,
    SessionStatus,
    StepRecord,
    VerificationItem,
)
from .serializers import (
    encode_screenshot_base64,
    make_initial_snapshot,
    serialize_step_actions,
)


class SessionState:
    def __init__(self, session_id: str, idle_timeout_seconds: float):
        self._idle_timeout_seconds = idle_timeout_seconds
        self._steps: list[StepRecord] = []
        self._messages: list[ChatMessage] = []
        self._pending_verification_items: dict[str, VerificationItem] = {}
        self._run_sequence = 0
        self._assistant_message_emitted = False
        self._latest_snapshot = make_initial_snapshot(session_id=session_id)

    @property
    def snapshot(self) -> SessionSnapshot:
        return self._latest_snapshot

    def snapshot_copy(self) -> SessionSnapshot:
        return self._latest_snapshot.model_copy(deep=True)

    def steps_copy(self, after_step_id: int | None = None) -> list[StepRecord]:
        if after_step_id is None:
            steps = self._steps
        else:
            steps = [step for step in self._steps if step.step_id > after_step_id]
        return [step.model_copy(deep=True) for step in steps]

    def prepare_start(self, query: str) -> None:
        self._append_message("user", query)
        self._latest_snapshot.request_text = query
        self.begin_run()

    def append_user_message(self, text: str) -> None:
        self._append_message("user", text)
        self._touch_snapshot()

    def begin_run(self) -> None:
        self._run_sequence += 1
        self._assistant_message_emitted = False
        self._latest_snapshot.status = SessionStatus.RUNNING
        self._latest_snapshot.current_run_id = f"run-{self._run_sequence:04d}"
        self._latest_snapshot.last_run_status = None
        self._latest_snapshot.waiting_reason = None
        self._latest_snapshot.expires_at = None
        self._latest_snapshot.final_reasoning = None
        self._latest_snapshot.run_summary = None
        self._latest_snapshot.final_result_summary = None
        self._latest_snapshot.last_reasoning = None
        self._latest_snapshot.last_actions = []
        self._latest_snapshot.error_message = None
        self._touch_snapshot()

    def enter_waiting_state(
        self,
        *,
        run_status: Literal["complete", "stopped"],
    ) -> None:
        self._latest_snapshot.status = SessionStatus.WAITING_FOR_INPUT
        self._latest_snapshot.last_run_status = run_status
        self._latest_snapshot.last_completed_run_id = self._latest_snapshot.current_run_id
        self._latest_snapshot.current_run_id = None
        self._latest_snapshot.waiting_reason = "follow_up"
        self._latest_snapshot.expires_at = time.time() + self._idle_timeout_seconds
        self._touch_snapshot()

    def mark_stopped(self, error_message: str | None = None) -> None:
        self._latest_snapshot.status = SessionStatus.STOPPED
        self._latest_snapshot.last_run_status = "stopped"
        self._latest_snapshot.current_run_id = None
        self._latest_snapshot.waiting_reason = None
        self._latest_snapshot.expires_at = None
        if error_message is not None:
            self._latest_snapshot.error_message = error_message
        self._touch_snapshot()

    def mark_error(self, error_message: str) -> None:
        self._latest_snapshot.status = SessionStatus.ERROR
        self._latest_snapshot.last_run_status = "error"
        self._latest_snapshot.waiting_reason = None
        self._latest_snapshot.expires_at = None
        self._latest_snapshot.error_message = error_message
        self._touch_snapshot()

    def finalize_run(self, final_reasoning: str | None) -> None:
        if final_reasoning:
            self._latest_snapshot.final_reasoning = final_reasoning
            if not self._assistant_message_emitted:
                self._append_message("assistant", final_reasoning)
                self._assistant_message_emitted = True
        self._touch_snapshot()

    def handle_agent_event(self, event: dict[str, Any]) -> None:
        event_type = event["type"]
        step_id = event.get("step_id")
        if event_type == "step_started":
            if not isinstance(step_id, int):
                return
            step = StepRecord(
                step_id=step_id,
                run_id=self._latest_snapshot.current_run_id,
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
                action_summary=None,
                reason=None,
                summary_source=None,
                user_visible_label=None,
                ambiguity_flag=None,
                ambiguity_type=None,
                ambiguity_message=None,
                review_evidence=[],
            )
            self._steps.append(step)
            self._latest_snapshot.latest_step_id = step.step_id
        elif event_type == "reasoning_extracted":
            step = self._get_step(step_id)
            if step:
                step.reasoning = event.get("reasoning")
            self._latest_snapshot.last_reasoning = event.get("reasoning")
            if event.get("reasoning"):
                self._latest_snapshot.run_summary = event.get("reasoning")
        elif event_type == "function_calls_extracted":
            step = self._get_step(step_id)
            serialized_actions = serialize_step_actions(event.get("function_calls", []))
            if step:
                step.function_calls = serialized_actions
            self._latest_snapshot.last_actions = serialized_actions
        elif event_type == "action_executed":
            self._handle_action_executed(step_id=step_id, payload=event)
        elif event_type == "review_metadata_extracted":
            self._apply_review_metadata(step_id=step_id, payload=event)
        elif event_type == "step_complete":
            step = self._get_step(step_id)
            if step:
                step.status = event.get("status", "complete")
            self._apply_review_metadata(step_id=step_id, payload=event)
            final_reasoning = event.get("final_reasoning")
            if final_reasoning:
                self._latest_snapshot.final_reasoning = final_reasoning
                self._latest_snapshot.run_summary = final_reasoning
                if not self._latest_snapshot.final_result_summary:
                    self._latest_snapshot.final_result_summary = final_reasoning
                if not self._assistant_message_emitted:
                    self._append_message("assistant", final_reasoning)
                    self._assistant_message_emitted = True
        elif event_type == "step_error":
            step = self._get_step(step_id)
            if step:
                step.status = "error"
                step.error_message = event.get("error_message")
            self._latest_snapshot.status = SessionStatus.ERROR
            self._latest_snapshot.last_run_status = "error"
            self._latest_snapshot.waiting_reason = None
            self._latest_snapshot.error_message = event.get("error_message")
        self._touch_snapshot()

    def _handle_action_executed(self, step_id: int | None, payload: dict[str, Any]) -> None:
        step = self._get_step(step_id)
        env_state = payload.get("env_state") or {}
        artifacts = payload.get("artifacts") or {}
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
            self._latest_snapshot.latest_screenshot_b64 = encode_screenshot_base64(screenshot)
        self._resolve_verification_items()

    def _append_message(
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

    def _apply_review_metadata(
        self,
        step_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        step = self._get_step(step_id)
        if step:
            _SIMPLE_REVIEW_FIELDS = (
                "phase_id", "phase_label", "phase_summary",
                "action_summary", "reason", "summary_source",
                "user_visible_label",
                "ambiguity_flag", "ambiguity_type", "ambiguity_message",
                "a11y_path",
            )
            for field in _SIMPLE_REVIEW_FIELDS:
                if field in payload:
                    setattr(step, field, payload.get(field))
            if "review_evidence" in payload:
                step.review_evidence = list(payload.get("review_evidence") or [])

        run_summary = payload.get("run_summary")
        if run_summary:
            self._latest_snapshot.run_summary = run_summary

        final_result_summary = payload.get("final_result_summary")
        if final_result_summary:
            self._latest_snapshot.final_result_summary = final_result_summary

        verification_items = payload.get("verification_items")
        if verification_items:
            self._record_verification_items(verification_items)
        self._resolve_verification_items()

    def _record_verification_items(self, items: list[dict[str, Any]]) -> None:
        for item_payload in items:
            source_step_id = item_payload.get("source_step_id")
            if source_step_id is None:
                continue
            item = VerificationItem(
                id=str(item_payload["id"]),
                message=str(item_payload["message"]),
                detail=item_payload.get("detail"),
                run_id=None,
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

    def _resolve_verification_items(self) -> None:
        resolved_items: list[VerificationItem] = []
        for item in self._pending_verification_items.values():
            step = self._get_step(item.source_step_id)
            if step is None:
                continue
            resolved_items.append(
                item.model_copy(
                    update={
                        "source_url": step.url,
                        "run_id": step.run_id,
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
                        "ambiguity_message": item.ambiguity_message or step.ambiguity_message,
                        "review_evidence": item.review_evidence or step.review_evidence,
                    }
                )
            )
        self._latest_snapshot.verification_items = [
            item.model_copy(deep=True) for item in resolved_items
        ]

    def _get_step(self, step_id: int | None) -> StepRecord | None:
        if step_id is None:
            return None
        for step in reversed(self._steps):
            if step.step_id == step_id:
                return step
        return None

    def _touch_snapshot(self) -> None:
        self._latest_snapshot.updated_at = time.time()
