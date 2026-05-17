"""Planner subgoal execution glue for BrowserAgent."""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

from google.genai.types import Content, Part

from agents.types import AgentRunResult, Subgoal
from . import subgoals as subgoal_helpers

SubgoalOutcome = tuple[Subgoal, Literal["done", "failed"], str]


def _format_prior_outcomes(outcomes: list[SubgoalOutcome]) -> str:
    if not outcomes:
        return "None yet."
    lines = []
    for subgoal, result, reason in outcomes:
        compact_reason = " ".join(reason.split())[:500]
        lines.append(f"- [{subgoal.id}] {result}: {subgoal.description} — {compact_reason}")
    return "\n".join(lines)


def _subgoal_prompt(agent: Any, subgoal: Subgoal, prior_outcomes: list[SubgoalOutcome]) -> str:
    latest_url = agent.latest_url or "unknown"
    scope = getattr(agent, "_navigation_scope", None)
    scope_text = getattr(scope, "description", "No explicit navigation scope.")
    return (
        f"Overall task context (reference only):\n{agent._query}\n\n"
        f"Task navigation scope:\n{scope_text}\n\n"
        f"Latest browser URL before this subgoal: {latest_url}\n\n"
        "Prior subgoal outcomes (compact summary, not full trajectory):\n"
        f"{_format_prior_outcomes(prior_outcomes)}\n\n"
        "Your only executable objective in this loop is the current subgoal. "
        "Use the overall task only as background context for interpreting scope, "
        "references, and constraints. Do not continue to the next subgoal or "
        "complete extra parts of the overall task after this subgoal is satisfied.\n\n"
        f"[Subgoal {subgoal.id}] {subgoal.description}\n"
        f"Success criteria: {subgoal.success_criteria}\n"
        "When you determine the success criteria is met, stop calling tools and "
        "respond with a final message that begins with either 'SUBGOAL_DONE:' "
        "(criteria satisfied) or 'SUBGOAL_FAILED:' (criteria cannot be met), "
        "followed by a short explanation."
    )


def run_subgoal_loop(
    agent: Any,
    subgoal: Subgoal,
    prior_outcomes: list[SubgoalOutcome] | None = None,
) -> tuple[Literal["done", "failed"], str]:
    """Run one planner subgoal using the BrowserAgent iteration contract."""
    prior_outcomes = prior_outcomes or []
    agent.final_reasoning = None
    agent._current_subgoal_id = subgoal.id
    agent._contents = [
        Content(
            role="user",
            parts=[Part(text=_subgoal_prompt(agent, subgoal, prior_outcomes))],
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


def run_subgoal_plan(agent: Any) -> AgentRunResult:
    """Run the BrowserAgent planner queue, including failure/replan glue."""
    queue = list(agent._subgoals)
    agent._raise_if_subgoal_budget_exceeded(len(queue))
    outcomes: list[SubgoalOutcome] = []
    index = 0
    blocked_reason: str | None = None
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
        result, reason = agent._run_subgoal_loop(active_subgoal, outcomes)
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
                revised = agent._replan_callback(
                    completed_subgoal,
                    reason,
                    remaining,
                    outcomes=outcomes,
                    latest_url=agent.latest_url,
                )
            except Exception as exc:  # noqa: BLE001
                blocked_reason = f"Replan failed after subgoal {completed_subgoal.id}: {exc}"
                agent._emit_event(
                    "replan_error",
                    subgoal_id=completed_subgoal.id,
                    error_message=str(exc),
                )
                return agent._finalize_subgoal_plan(
                    outcomes,
                    status="blocked",
                    reason=blocked_reason,
                )
            if not revised:
                blocked_reason = (
                    f"Replan returned no replacement subgoals after subgoal {completed_subgoal.id} failed."
                )
                agent._emit_event(
                    "replan_error",
                    subgoal_id=completed_subgoal.id,
                    error_message=blocked_reason,
                )
                return agent._finalize_subgoal_plan(
                    outcomes,
                    status="blocked",
                    reason=blocked_reason,
                )
            queue = queue[: index + 1] + list(revised)
            agent._raise_if_subgoal_budget_exceeded(len(queue))
        index += 1
    status = "complete" if all(result == "done" for _, result, _ in outcomes) else "partial_failure"
    return agent._finalize_subgoal_plan(outcomes, status=status, reason=blocked_reason)
