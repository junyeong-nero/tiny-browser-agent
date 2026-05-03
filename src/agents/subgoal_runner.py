"""Planner subgoal execution glue for BrowserAgent."""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

from google.genai.types import Content, Part

from agents import subgoals as subgoal_helpers
from agents.types import Subgoal


def run_subgoal_loop(agent: Any, subgoal: Subgoal) -> tuple[Literal["done", "failed"], str]:
    """Run one planner subgoal using the BrowserAgent iteration contract."""
    agent.final_reasoning = None
    agent._current_subgoal_id = subgoal.id
    agent._contents = [
        Content(
            role="user",
            parts=[
                Part(
                    text=(
                        f"[Subgoal {subgoal.id}] {subgoal.description}\n"
                        f"Success criteria: {subgoal.success_criteria}\n"
                        "When you determine the success criteria is met, stop calling tools and "
                        "respond with a final message that begins with either 'SUBGOAL_DONE:' "
                        "(criteria satisfied) or 'SUBGOAL_FAILED:' (criteria cannot be met), "
                        "followed by a short explanation."
                    )
                )
            ],
        )
    ]
    try:
        status = "CONTINUE"
        steps = 0
        while status == "CONTINUE":
            agent._raise_if_interrupted()
            agent._raise_if_total_step_budget_exceeded()
            if steps >= agent._max_steps_per_subgoal:
                return "failed", (
                    f"Exceeded max steps ({agent._max_steps_per_subgoal}) for subgoal {subgoal.id}."
                )
            status = agent.run_one_iteration()
            steps += 1
            agent._total_steps_used += 1
            final_text = (agent.final_reasoning or "").strip()
            if status == "COMPLETE" and not subgoal_helpers.has_subgoal_marker(final_text):
                if steps >= agent._max_steps_per_subgoal:
                    break
                agent.append_user_message(
                    "The previous turn ended this subgoal without the required "
                    "SUBGOAL_DONE: or SUBGOAL_FAILED: marker. Inspect the latest "
                    "browser state and respond with exactly one final subgoal "
                    "status message using the required marker. If the previous "
                    "turn produced no text because of a transient model error, "
                    "retry the subgoal decision now."
                )
                agent.final_reasoning = None
                status = "CONTINUE"
    finally:
        agent._current_subgoal_id = None

    return subgoal_helpers.classify_subgoal_final_text(
        subgoal_id=subgoal.id,
        final_text=agent.final_reasoning or "",
        steps=steps,
    )


def run_subgoal_plan(agent: Any) -> None:
    """Run the BrowserAgent planner queue, including failure/replan glue."""
    queue = list(agent._subgoals)
    agent._raise_if_subgoal_budget_exceeded(len(queue))
    outcomes: list[tuple[Subgoal, Literal["done", "failed"], str]] = []
    index = 0
    while index < len(queue):
        agent._raise_if_interrupted()
        active_subgoal = dataclasses.replace(queue[index], status="active")
        queue[index] = active_subgoal
        agent._emit_event(
            "subgoal_started",
            subgoal_id=active_subgoal.id,
            description=active_subgoal.description,
            success_criteria=active_subgoal.success_criteria,
        )
        result, reason = agent._run_subgoal_loop(active_subgoal)
        completed_subgoal = dataclasses.replace(active_subgoal, status=result)
        queue[index] = completed_subgoal
        outcomes.append((completed_subgoal, result, reason))
        agent._emit_event(
            "subgoal_completed" if result == "done" else "subgoal_failed",
            subgoal_id=completed_subgoal.id,
            status=result,
            reason=reason,
        )
        if result == "failed" and agent._replan_callback is not None:
            remaining = queue[index + 1 :]
            try:
                revised = agent._replan_callback(completed_subgoal, reason, remaining)
            except Exception as exc:  # noqa: BLE001
                agent._emit_event(
                    "replan_error",
                    subgoal_id=completed_subgoal.id,
                    error_message=str(exc),
                )
                return
            queue = queue[: index + 1] + list(revised)
            agent._raise_if_subgoal_budget_exceeded(len(queue))
        index += 1
    agent._finalize_subgoal_plan(outcomes)
