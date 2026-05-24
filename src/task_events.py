"""Shared task metadata and terminal event builders."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_session_metadata(
    *,
    query: str,
    model_name: str,
    grounding: str,
    started_at: datetime,
    use_planner: bool,
    video_enabled: bool,
    constraints: Any,
) -> dict[str, Any]:
    return {
        "query": query,
        "model_name": model_name,
        "grounding": grounding,
        "started_at": started_at.isoformat(timespec="seconds"),
        "use_planner": use_planner,
        "video_enabled": video_enabled,
        "constraints": constraints.model_dump(),
    }


def result_status(result: Any) -> str:
    status = getattr(result, "status", "complete")
    return status if isinstance(status, str) else "complete"


def _with_task_id(event: dict[str, Any], task_id: int | None) -> dict[str, Any]:
    if task_id is not None:
        event["task_id"] = task_id
    return event


def build_task_failed_event_from_result(
    *,
    query: str,
    result: Any,
    task_id: int | None = None,
    terminal_step_id: int | None = None,
) -> dict[str, Any]:
    return _with_task_id(
        {
            "type": "task_failed",
            "query": query,
            "status": result_status(result),
            "error_message": (
                getattr(result, "reason", None)
                or getattr(result, "summary", None)
                or "Task did not complete successfully."
            ),
            "succeeded_subgoals": getattr(result, "succeeded_subgoals", 0),
            "failed_subgoals": getattr(result, "failed_subgoals", 0),
            # Outcome metadata consumed by graph dead-end / dead-action cues
            # (outline §F2). task_success=False ⇒ terminal step is a candidate.
            "task_success": False,
            "terminal_step_id": terminal_step_id,
        },
        task_id,
    )


def build_task_failed_event(
    *,
    query: str,
    error_message: str,
    task_id: int | None = None,
    terminal_step_id: int | None = None,
) -> dict[str, Any]:
    return _with_task_id(
        {
            "type": "task_failed",
            "query": query,
            "status": "failed",
            "error_message": error_message,
            "task_success": False,
            "terminal_step_id": terminal_step_id,
        },
        task_id,
    )


def build_task_interrupted_event(
    *,
    query: str,
    reason: str,
    task_id: int | None = None,
    terminal_step_id: int | None = None,
) -> dict[str, Any]:
    return _with_task_id(
        {
            "type": "task_interrupted",
            "query": query,
            "reason": reason,
            "task_success": False,
            "terminal_step_id": terminal_step_id,
        },
        task_id,
    )


def final_reasoning_from_agent_result(agent: Any, result: Any) -> str | None:
    final_reasoning = getattr(agent, "final_reasoning", None)
    if isinstance(final_reasoning, str) and final_reasoning.strip():
        return final_reasoning
    result_summary = getattr(result, "summary", None)
    if isinstance(result_summary, str) and result_summary.strip():
        return result_summary
    return None


def build_task_complete_event(
    *,
    query: str,
    agent: Any,
    result: Any,
    task_id: int | None = None,
    terminal_step_id: int | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = _with_task_id(
        {
            "type": "task_complete",
            "query": query,
            "status": "complete",
            "task_success": True,
            "terminal_step_id": terminal_step_id,
        },
        task_id,
    )
    final_reasoning = final_reasoning_from_agent_result(agent, result)
    if final_reasoning is not None:
        event["final_reasoning"] = final_reasoning
    return event
