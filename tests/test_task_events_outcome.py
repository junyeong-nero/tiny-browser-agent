"""P3: task lifecycle events must carry outcome metadata so the UI graph can
fire dead-end / dead-action cues per outline §F2."""

from __future__ import annotations

from types import SimpleNamespace

from task_events import (
    build_task_complete_event,
    build_task_failed_event_from_result,
)


def test_complete_event_marks_success_and_terminal_step():
    agent = SimpleNamespace(final_reasoning="all done")
    result = SimpleNamespace(status="complete", summary="ok")
    event = build_task_complete_event(
        query="q",
        agent=agent,
        result=result,
        task_id=1,
        terminal_step_id=42,
    )
    assert event["type"] == "task_complete"
    assert event["task_success"] is True
    assert event["terminal_step_id"] == 42


def test_failed_event_marks_failure_and_terminal_step():
    result = SimpleNamespace(
        status="failed",
        reason="step error",
        succeeded_subgoals=2,
        failed_subgoals=1,
    )
    event = build_task_failed_event_from_result(
        query="q",
        result=result,
        task_id=7,
        terminal_step_id=11,
    )
    assert event["type"] == "task_failed"
    assert event["task_success"] is False
    assert event["terminal_step_id"] == 11
    assert event["error_message"] == "step error"


def test_failed_event_allows_missing_terminal_step():
    # Errors before the first action still emit terminal events; graph
    # gracefully skips dead-end cue when terminal_step_id is None.
    result = SimpleNamespace(status="failed", reason="setup failed")
    event = build_task_failed_event_from_result(query="q", result=result)
    assert event["task_success"] is False
    assert event["terminal_step_id"] is None
