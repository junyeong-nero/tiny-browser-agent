import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from agents.planner_agent import PlannerAgent
from agents.types import Subgoal


def _mock_llm_client(subgoals_data: list[dict]) -> MagicMock:
    client = MagicMock()
    part = MagicMock()
    part.text = json.dumps(subgoals_data)
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]
    client.generate_content.return_value = response
    return client


SAMPLE_PLAN = [
    {"id": 1, "description": "Open Google", "success_criteria": "Google homepage loaded"},
    {"id": 2, "description": "Search for Python", "success_criteria": "Search results shown"},
]


class TestPlannerAgentPlan:
    def test_returns_list_of_subgoals(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="search Python on Google", llm_client=client)

        subgoals = planner.plan()

        assert len(subgoals) == 2
        assert all(isinstance(sg, Subgoal) for sg in subgoals)

    def test_subgoal_ids_start_at_one(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="test", llm_client=client)
        subgoals = planner.plan()
        assert subgoals[0].id == 1
        assert subgoals[1].id == 2

    def test_subgoal_fields(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="test", llm_client=client)
        subgoals = planner.plan()
        assert subgoals[0].description == "Open Google"
        assert subgoals[0].success_criteria == "Google homepage loaded"
        assert subgoals[0].status == "pending"

    def test_calls_llm_once(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="test", llm_client=client)
        planner.plan()
        assert client.generate_content.call_count == 1

    def test_uses_json_response_mime_type(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="test", llm_client=client)
        planner.plan()
        call_kwargs = client.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs.args[2]
        assert config.response_mime_type == "application/json"

    def test_uses_system_instruction_for_planning_prompt(self):
        client = _mock_llm_client(SAMPLE_PLAN)
        planner = PlannerAgent(query="test", llm_client=client)
        planner.plan()

        call_kwargs = client.generate_content.call_args
        contents = call_kwargs.kwargs.get("contents") or call_kwargs.args[1]
        config = call_kwargs.kwargs.get("config") or call_kwargs.args[2]

        system_text = "\n".join(
            part.text or "" for part in config.system_instruction.parts or []
        )
        user_text = "\n".join(part.text or "" for part in contents[0].parts or [])

        assert "planning agent for a web browser automation system" in system_text
        assert "Respond ONLY with a JSON array of subgoals" in system_text
        assert user_text == "User query:\ntest"

    def test_invalid_json_no_array_returns_empty_list(self):
        client = MagicMock()
        part = MagicMock()
        part.text = "not valid json at all"
        content = MagicMock()
        content.parts = [part]
        candidate = MagicMock()
        candidate.content = content
        response = MagicMock()
        response.candidates = [candidate]
        client.generate_content.return_value = response

        planner = PlannerAgent(query="test", llm_client=client)
        subgoals = planner.plan()
        assert subgoals == []

    def test_empty_plan(self):
        client = _mock_llm_client([])
        planner = PlannerAgent(query="test", llm_client=client)
        subgoals = planner.plan()
        assert subgoals == []


class TestPlannerAgentReplan:
    def test_replan_returns_subgoals(self):
        new_plan = [
            {"id": 3, "description": "Try Bing instead", "success_criteria": "Bing loaded"},
        ]
        client = _mock_llm_client(new_plan)
        planner = PlannerAgent(query="search Python", llm_client=client)

        failed = Subgoal(id=2, description="Search on Google", success_criteria="Results shown")
        remaining = [Subgoal(id=3, description="Click first result", success_criteria="Page opened")]

        subgoals = planner.replan(
            current_subgoal=failed,
            failure_reason="Page not responding",
            remaining=remaining,
        )

        assert len(subgoals) == 1
        assert subgoals[0].id == 3  # start_id = failed.id + 1 = 3

    def test_replan_start_id_after_failed(self):
        new_plan = [
            {"id": 99, "description": "Fallback step", "success_criteria": "Done"},
        ]
        client = _mock_llm_client(new_plan)
        planner = PlannerAgent(query="test", llm_client=client)

        failed = Subgoal(id=5, description="Failed step", success_criteria="N/A")
        subgoals = planner.replan(
            current_subgoal=failed,
            failure_reason="Timeout",
            remaining=[],
        )
        # start_id = 5 + 1 = 6, so first new subgoal gets id 6 (index 0 + start_id)
        assert subgoals[0].id == 6

    def test_replan_completed_event_includes_failed_subgoal_id(self):
        events = []
        client = _mock_llm_client(
            [{"id": 99, "description": "Fallback step", "success_criteria": "Done"}]
        )
        planner = PlannerAgent(query="test", llm_client=client, event_sink=events.append)

        failed = Subgoal(id=5, description="Failed step", success_criteria="N/A")
        planner.replan(
            current_subgoal=failed,
            failure_reason="Timeout",
            remaining=[],
        )

        replanned = next(event for event in events if event["type"] == "planner_replanned")
        assert replanned["failed_subgoal_id"] == 5

    def test_replan_uses_replan_system_instruction(self):
        client = _mock_llm_client(
            [{"id": 99, "description": "Fallback step", "success_criteria": "Done"}]
        )
        planner = PlannerAgent(query="test", llm_client=client)

        failed = Subgoal(id=5, description="Failed step", success_criteria="N/A")
        planner.replan(
            current_subgoal=failed,
            failure_reason="Timeout",
            remaining=[],
        )

        call_kwargs = client.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs.args[2]
        system_text = "\n".join(
            part.text or "" for part in config.system_instruction.parts or []
        )

        assert "A subgoal has failed or become blocked" in system_text
        assert "Avoid repeating the failed path" in system_text
