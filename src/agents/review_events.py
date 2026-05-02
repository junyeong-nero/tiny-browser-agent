"""Helpers for UI-facing action review event payloads."""

from __future__ import annotations

from typing import Any, Optional


def build_review_metadata_event_payload(
    *,
    step_id: int,
    step_review_metadata: dict[str, Any],
    reasoning: Optional[str],
    final_result_summary: Optional[str],
    current_subgoal_id: int | None,
) -> dict[str, Any]:
    if final_result_summary is not None:
        default_phase_id = "phase-complete"
        default_phase_label = "완료"
        default_user_visible_label = "결과 정리"
    else:
        default_phase_id = "all-steps"
        default_phase_label = "전체 과정 보기"
        default_user_visible_label = f"Step {step_id}"

    return {
        "step_id": step_id,
        "subgoal_id": step_review_metadata.get("subgoal_id", current_subgoal_id),
        "phase_id": step_review_metadata.get("phase_id", default_phase_id),
        "phase_label": step_review_metadata.get("phase_label", default_phase_label),
        "phase_summary": step_review_metadata.get("phase_summary", reasoning),
        "what": step_review_metadata.get("what"),
        "why": step_review_metadata.get("why"),
        "outcome": step_review_metadata.get("outcome"),
        "action_summary": step_review_metadata.get(
            "action_summary",
            step_review_metadata.get("user_visible_label", default_user_visible_label),
        ),
        "reason": step_review_metadata.get("reason", reasoning),
        "summary_source": step_review_metadata.get("summary_source", "app_derived"),
        "user_visible_label": step_review_metadata.get(
            "user_visible_label",
            default_user_visible_label,
        ),
        "verification_items": step_review_metadata.get("verification_items", []),
        "run_summary": final_result_summary or reasoning,
        "final_result_summary": final_result_summary,
        "ambiguity_flag": step_review_metadata.get("ambiguity_flag"),
        "ambiguity_type": step_review_metadata.get("ambiguity_type"),
        "ambiguity_message": step_review_metadata.get("ambiguity_message"),
        "review_evidence": step_review_metadata.get("review_evidence", []),
        "a11y_path": step_review_metadata.get("a11y_path"),
    }
