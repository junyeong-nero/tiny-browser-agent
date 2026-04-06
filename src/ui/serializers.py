import base64
import time

from .models import SessionSnapshot, SessionStatus, StepAction


def encode_screenshot_base64(screenshot: bytes | None) -> str | None:
    if screenshot is None:
        return None
    return base64.b64encode(screenshot).decode("ascii")


def make_initial_snapshot(session_id: str, artifacts_base_url: str) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=session_id,
        status=SessionStatus.IDLE,
        current_url=None,
        latest_screenshot_b64=None,
        latest_step_id=None,
        last_reasoning=None,
        last_actions=[],
        messages=[],
        final_reasoning=None,
        error_message=None,
        artifacts_base_url=artifacts_base_url,
        updated_at=time.time(),
    )


def serialize_step_actions(actions: list[dict]) -> list[StepAction]:
    return [
        StepAction(name=action["name"], args=dict(action.get("args") or {}))
        for action in actions
    ]
