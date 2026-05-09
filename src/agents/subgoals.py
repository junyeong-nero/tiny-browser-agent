"""Subgoal result helpers for planner-driven actor runs."""

from __future__ import annotations

from typing import Literal

from agents.types import Subgoal

SubgoalOutcome = tuple[Subgoal, Literal["done", "failed"], str]


def has_subgoal_marker(final_text: str) -> bool:
    upper = final_text.upper()
    return "SUBGOAL_DONE" in upper or "SUBGOAL_FAILED" in upper


def classify_subgoal_final_text(
    *,
    subgoal_id: int,
    final_text: str,
    steps: int,
) -> tuple[Literal["done", "failed"], str]:
    final_text = final_text.strip()
    if not final_text:
        return "failed", (
            f"Subgoal {subgoal_id} did not produce a final status message after "
            f"{steps} step(s)."
        )
    upper = final_text.upper()
    if "SUBGOAL_FAILED" in upper:
        return "failed", final_text
    if "SUBGOAL_DONE" in upper:
        return "done", final_text
    return "failed", (
        f"Subgoal {subgoal_id} completed without declaring success. Final text: {final_text[:200]}"
    )


def build_subgoal_plan_summary(outcomes: list[SubgoalOutcome]) -> str:
    succeeded = sum(1 for _, result, _ in outcomes if result == "done")
    failed = sum(1 for _, result, _ in outcomes if result == "failed")
    header = (
        "All planner subgoals completed."
        if failed == 0
        else "Planner subgoals completed with failures."
    )
    lines = [header, f"Subgoal outcomes: {succeeded} succeeded, {failed} failed."]
    for subgoal, result, reason in outcomes:
        lines.append(f"[{subgoal.id}] {subgoal.description}: {reason} (status: {result})")
    if failed:
        lines.append("Failure reasons:")
        for subgoal, result, reason in outcomes:
            if result == "failed":
                lines.append(f"- [{subgoal.id}] {reason}")
    return "\n".join(lines)
