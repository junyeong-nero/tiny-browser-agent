from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"


class StepAction(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class VerificationItem(BaseModel):
    id: str
    message: str
    detail: str | None = None
    run_id: str | None = None
    source_step_id: int | None = None
    source_url: str | None = None
    screenshot_path: str | None = None
    html_path: str | None = None
    metadata_path: str | None = None
    a11y_path: str | None = None
    ambiguity_flag: bool | None = None
    ambiguity_type: str | None = None
    ambiguity_message: str | None = None
    review_evidence: list[str] = Field(default_factory=list)
    status: Literal["needs_review", "resolved"]


class StepRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    step_id: int
    run_id: str | None = None
    timestamp: float
    reasoning: str | None = None
    function_calls: list[StepAction] = Field(default_factory=list)
    url: str | None = None
    status: Literal["running", "complete", "error"]
    screenshot_path: str | None = None
    html_path: str | None = None
    metadata_path: str | None = None
    a11y_path: str | None = None
    error_message: str | None = None
    phase_id: str | None = None
    phase_label: str | None = None
    phase_summary: str | None = None
    user_visible_label: str | None = None
    ambiguity_flag: bool | None = None
    ambiguity_type: str | None = None
    ambiguity_message: str | None = None
    review_evidence: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    text: str
    timestamp: float


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    status: SessionStatus
    current_run_id: str | None = None
    last_completed_run_id: str | None = None
    last_run_status: Literal["complete", "stopped", "error"] | None = None
    waiting_reason: Literal["follow_up", "confirmation"] | None = None
    expires_at: float | None = None
    current_url: str | None = None
    latest_screenshot_b64: str | None = None
    latest_step_id: int | None = None
    last_reasoning: str | None = None
    last_actions: list[StepAction] = Field(default_factory=list)
    messages: list[ChatMessage] = Field(default_factory=list)
    final_reasoning: str | None = None
    request_text: str | None = None
    run_summary: str | None = None
    verification_items: list[VerificationItem] = Field(default_factory=list)
    final_result_summary: str | None = None
    error_message: str | None = None
    updated_at: float


class VerificationGroup(BaseModel):
    id: str
    run_id: str | None = None
    label: str
    summary: str | None = None
    step_ids: list[int] = Field(default_factory=list)
    steps: list[StepRecord] = Field(default_factory=list)
    screenshot_path: str | None = None
    html_path: str | None = None
    metadata_path: str | None = None
    a11y_path: str | None = None


class VerificationPayload(BaseModel):
    session_id: str
    current_run_id: str | None = None
    last_completed_run_id: str | None = None
    request_text: str | None = None
    run_summary: str | None = None
    final_result_summary: str | None = None
    verification_items: list[VerificationItem] = Field(default_factory=list)
    grouped_steps: list[VerificationGroup] = Field(default_factory=list)


class CreatedSession(BaseModel):
    session_id: str
    snapshot: SessionSnapshot
