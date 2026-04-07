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
    source_step_id: int | None = None
    source_url: str | None = None
    screenshot_path: str | None = None
    html_path: str | None = None
    metadata_path: str | None = None
    status: Literal["needs_review", "resolved"]


class StepRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    step_id: int
    timestamp: float
    reasoning: str | None = None
    function_calls: list[StepAction] = Field(default_factory=list)
    url: str | None = None
    status: Literal["running", "complete", "error"]
    screenshot_path: str | None = None
    html_path: str | None = None
    metadata_path: str | None = None
    error_message: str | None = None
    phase_id: str | None = None
    phase_label: str | None = None
    phase_summary: str | None = None
    user_visible_label: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    text: str
    timestamp: float


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    session_id: str
    status: SessionStatus
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
    artifacts_base_url: str | None = None
    updated_at: float


class CreateSessionResponse(BaseModel):
    session_id: str
    snapshot: SessionSnapshot


class StartSessionRequest(BaseModel):
    query: str


class SendMessageRequest(BaseModel):
    text: str
