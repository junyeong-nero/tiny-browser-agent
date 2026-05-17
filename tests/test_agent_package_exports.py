import os
import subprocess
import sys

from agents.actor import AgentInterrupted, BrowserAgent
from agents.actor.agent import AgentInterrupted as DirectAgentInterrupted
from agents.actor.agent import BrowserAgent as DirectBrowserAgent
from agents.planner import PlannerAgent, _SubgoalSchema
from agents.planner.agent import PlannerAgent as DirectPlannerAgent
from agents.planner.agent import _SubgoalSchema as DirectSubgoalSchema
from agents.summarizer.agent import ActionReviewService as DirectActionReviewService
from agents.summarizer import ActionReviewService


def test_agent_packages_export_primary_classes_from_canonical_modules():
    assert BrowserAgent is DirectBrowserAgent
    assert AgentInterrupted is DirectAgentInterrupted
    assert PlannerAgent is DirectPlannerAgent
    assert _SubgoalSchema is DirectSubgoalSchema
    assert ActionReviewService is DirectActionReviewService


def test_helper_modules_are_imported_from_canonical_subpackages():
    from agents.actor import context_compaction, model_trace, model_turn, task_scope
    from agents.planner import subgoals

    assert context_compaction.__name__ == "agents.actor.context_compaction"
    assert model_trace.__name__ == "agents.actor.model_trace"
    assert model_turn.__name__ == "agents.actor.model_turn"
    assert task_scope.__name__ == "agents.actor.task_scope"
    assert subgoals.__name__ == "agents.planner.subgoals"


def test_removed_root_compatibility_modules_are_not_importable():
    script = """
import importlib.util

for name in [
    "agents.actor_agent",
    "agents.context_compaction",
    "agents.model_trace",
    "agents.model_turn",
    "agents.planner_agent",
    "agents.post_summary_agent",
    "agents.review_events",
    "agents.safety",
    "agents.subgoal_runner",
    "agents.subgoals",
    "agents.task_scope",
    "agents.tool_orchestration",
]:
    print(importlib.util.find_spec(name) is None)
"""
    env = {**os.environ, "PYTHONPATH": "src:."}
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.stdout.splitlines() == ["True"] * 12


def test_helper_submodule_imports_do_not_eager_load_heavy_agents():
    script = """
import importlib
import sys

importlib.import_module("agents.actor.task_scope")
importlib.import_module("agents.planner.subgoals")

print("agents.actor.agent" in sys.modules)
print("agents.planner.agent" in sys.modules)
"""
    env = {**os.environ, "PYTHONPATH": "src:."}
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]
