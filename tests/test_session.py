from pathlib import Path
from unittest.mock import MagicMock, patch

from session import BrowserSession


@patch("session.emit")
@patch("session.BrowserAgent")
@patch("agents.planner_agent.PlannerAgent")
def test_run_task_passes_planner_replan_callback(
    mock_planner_agent,
    mock_browser_agent,
    _mock_emit,
):
    browser = MagicMock()
    planner = mock_planner_agent.return_value
    subgoals = [MagicMock()]
    planner.plan.return_value = subgoals

    session = BrowserSession(
        browser_computer=browser,
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
        use_planner=True,
    )

    session.run_task("test query")

    call_kwargs = mock_browser_agent.call_args.kwargs
    assert call_kwargs["subgoals"] is subgoals
    assert call_kwargs["replan_callback"] is planner.replan


@patch("session.emit")
@patch("session.BrowserAgent")
def test_run_task_emits_task_failed_instead_of_complete_on_agent_error(
    mock_browser_agent,
    mock_emit,
):
    browser = MagicMock()
    mock_browser_agent.return_value.agent_loop.side_effect = RuntimeError("boom")
    session = BrowserSession(
        browser_computer=browser,
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )

    session.run_task("test query")

    emitted_types = [call.args[0]["type"] for call in mock_emit.call_args_list]
    assert "step_error" in emitted_types
    assert "task_failed" in emitted_types
    assert "task_complete" not in emitted_types
    browser.reset_to_blank.assert_called_once_with()
