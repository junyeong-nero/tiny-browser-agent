from pathlib import Path
from unittest.mock import MagicMock, patch

from session import MAX_CONVERSATION_MEMORY_ITEMS, BrowserSession, TaskMemory


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
    assert call_kwargs["conversation_context"] is None


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


@patch("session.emit")
@patch("session.BrowserAgent")
def test_run_task_passes_completed_task_memory_to_next_agent(
    mock_browser_agent,
    _mock_emit,
):
    browser = MagicMock()
    first_agent = MagicMock()
    first_agent.final_reasoning = "Found iPhone 17 Pro price."
    first_agent.latest_url = "https://example.com/iphone-17-pro"
    second_agent = MagicMock()
    second_agent.final_reasoning = "Found iPhone 16 Pro price."
    second_agent.latest_url = "https://example.com/iphone-16-pro"
    mock_browser_agent.side_effect = [first_agent, second_agent]
    session = BrowserSession(
        browser_computer=browser,
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )

    session.run_task("아이폰 17 Pro 가격을 검색해줘.")
    session.run_task("16 Pro 가격도 검색해줘.")

    first_call_kwargs = mock_browser_agent.call_args_list[0].kwargs
    second_call_kwargs = mock_browser_agent.call_args_list[1].kwargs
    assert first_call_kwargs["conversation_context"] is None
    assert "아이폰 17 Pro 가격을 검색해줘." in second_call_kwargs["conversation_context"]
    assert "Found iPhone 17 Pro price." in second_call_kwargs["conversation_context"]
    assert "https://example.com/iphone-17-pro" in second_call_kwargs["conversation_context"]


@patch("session.emit")
@patch("session.BrowserAgent")
def test_failed_task_is_not_added_to_conversation_memory(
    mock_browser_agent,
    _mock_emit,
):
    browser = MagicMock()
    failed_agent = MagicMock()
    failed_agent.agent_loop.side_effect = RuntimeError("boom")
    second_agent = MagicMock()
    second_agent.final_reasoning = "done"
    second_agent.latest_url = None
    mock_browser_agent.side_effect = [failed_agent, second_agent]
    session = BrowserSession(
        browser_computer=browser,
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )

    session.run_task("failing task")
    session.run_task("next task")

    second_call_kwargs = mock_browser_agent.call_args_list[1].kwargs
    assert second_call_kwargs["conversation_context"] is None


def test_conversation_memory_is_limited_and_compacts_results():
    browser = MagicMock()
    session = BrowserSession(
        browser_computer=browser,
        model_name="test_model",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )
    for index in range(MAX_CONVERSATION_MEMORY_ITEMS + 1):
        agent = MagicMock()
        agent.final_reasoning = f"result    {index}\nwith extra whitespace"
        agent.latest_url = f"https://example.com/{index}"
        session._remember_completed_task(f"query {index}", agent)

    memory = session._conversation_memory
    assert len(memory) == MAX_CONVERSATION_MEMORY_ITEMS
    assert memory[0] == TaskMemory(
        query="query 1",
        result="result 1 with extra whitespace",
        final_url="https://example.com/1",
    )


@patch("session.task_queue")
@patch("session.emit")
def test_run_emits_session_ready_with_model_name(mock_emit, mock_task_queue):
    browser = MagicMock()
    mock_task_queue.get.return_value = None
    session = BrowserSession(
        browser_computer=browser,
        model_name="nvidia/nemotron-3-super-120b-a12b:free",
        logs_dir=Path("logs/history"),
        log_enabled=False,
    )

    session.run()

    mock_emit.assert_any_call(
        {
            "type": "session_ready",
            "model_name": "nvidia/nemotron-3-super-120b-a12b:free",
        }
    )
