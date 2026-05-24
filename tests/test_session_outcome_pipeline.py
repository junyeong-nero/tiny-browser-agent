"""P6: outcome metadata (task_success, terminal_step_id) must reach the UI on
every BrowserSession.run_task lifecycle path so graph dead-end / dead-action
cues can fire downstream (outline §F2 + S2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.actor.agent import AgentInterrupted
from session import BrowserSession


def _session() -> BrowserSession:
    return BrowserSession(
        browser_computer=MagicMock(),
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )


def _terminal_event(mock_emit, event_type: str) -> dict:
    for call in mock_emit.call_args_list:
        event = call.args[0]
        if event.get("type") == event_type:
            return event
    raise AssertionError(f"No {event_type!r} event was emitted")


@patch("session.emit")
@patch("session.BrowserAgent")
def test_task_complete_carries_success_and_terminal_step(mock_browser_agent, mock_emit):
    agent_instance = mock_browser_agent.return_value
    agent_instance._step_id = 17
    agent_instance.agent_loop.return_value = MagicMock(status="complete")
    agent_instance.final_reasoning = "done"

    _session().run_task("q")

    event = _terminal_event(mock_emit, "task_complete")
    assert event["task_success"] is True
    assert event["terminal_step_id"] == 17


@patch("session.emit")
@patch("session.BrowserAgent")
def test_task_failed_from_non_complete_result_carries_failure_and_terminal_step(
    mock_browser_agent, mock_emit
):
    agent_instance = mock_browser_agent.return_value
    agent_instance._step_id = 9
    result = MagicMock(status="failed", reason="bad", succeeded_subgoals=0, failed_subgoals=1)
    agent_instance.agent_loop.return_value = result

    _session().run_task("q")

    event = _terminal_event(mock_emit, "task_failed")
    assert event["task_success"] is False
    assert event["terminal_step_id"] == 9


@patch("session.emit")
@patch("session.BrowserAgent")
def test_task_failed_from_agent_exception_carries_failure_and_terminal_step(
    mock_browser_agent, mock_emit
):
    agent_instance = mock_browser_agent.return_value
    agent_instance._step_id = 4
    agent_instance.agent_loop.side_effect = RuntimeError("boom")

    _session().run_task("q")

    event = _terminal_event(mock_emit, "task_failed")
    assert event["task_success"] is False
    assert event["terminal_step_id"] == 4


@patch("session.emit")
@patch("session.BrowserAgent")
def test_task_interrupted_carries_failure_and_terminal_step(mock_browser_agent, mock_emit):
    agent_instance = mock_browser_agent.return_value
    agent_instance._step_id = 22
    agent_instance.agent_loop.side_effect = AgentInterrupted("stopped")

    _session().run_task("q")

    event = _terminal_event(mock_emit, "task_interrupted")
    assert event["task_success"] is False
    assert event["terminal_step_id"] == 22


@patch("session.emit")
@patch("session.BrowserAgent")
def test_task_failed_before_agent_built_emits_null_terminal_step(
    mock_browser_agent, mock_emit
):
    # Setup failure: BrowserAgent ctor explodes before any action runs. The
    # outer except still emits task_failed with task_success=False and a null
    # terminal_step_id since no step ever executed.
    mock_browser_agent.side_effect = RuntimeError("setup boom")

    _session().run_task("q")

    event = _terminal_event(mock_emit, "task_failed")
    assert event["task_success"] is False
    assert event["terminal_step_id"] is None
