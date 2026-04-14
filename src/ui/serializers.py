import base64
import time

from .models import SessionSnapshot, SessionStatus, StepAction


def encode_screenshot_base64(screenshot: bytes | None) -> str | None:
    if screenshot is None:
        return None
    return base64.b64encode(screenshot).decode("ascii")


def make_initial_snapshot(session_id: str) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=session_id,
        status=SessionStatus.IDLE,
        current_run_id=None,
        last_completed_run_id=None,
        last_run_status=None,
        waiting_reason=None,
        expires_at=None,
        current_url=None,
        latest_screenshot_b64=None,
        latest_step_id=None,
        last_reasoning=None,
        last_actions=[],
        messages=[],
        final_reasoning=None,
        request_text=None,
        run_summary=None,
        verification_items=[],
        final_result_summary=None,
        error_message=None,
        updated_at=time.time(),
    )


def serialize_step_actions(actions: list[dict]) -> list[StepAction]:
    return [
        StepAction(name=action["name"], args=dict(action.get("args") or {}))
        for action in actions
    ]
