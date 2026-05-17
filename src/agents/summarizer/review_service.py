from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from google.genai import types

from .ambiguity import (
    ActionReviewContext,
    AmbiguityCandidate,
    detect_ambiguity_candidate,
)
from .formatters import (
    DEFAULT_PHASE,
    NAVIGATION_ACTION_NAMES,
    PHASE_GROUPS,
    build_action_summary,
    build_fallback_reason,
)
from .types import ActionStepSummarizerProtocol, ActionStepSummary


def _ambiguity_fields(
    ambiguity_candidate: AmbiguityCandidate | None,
) -> dict[str, Any]:
    return {
        "ambiguity_flag": ambiguity_candidate is not None,
        "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
        "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
        "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
    }


def _action_summary_fields(action_step_summary: ActionStepSummary) -> dict[str, Any]:
    return {
        "what": action_step_summary.what,
        "why": action_step_summary.why,
        "outcome": action_step_summary.outcome,
        "action_summary": action_step_summary.action_summary,
        "reason": action_step_summary.reason,
        "summary_source": action_step_summary.summary_source,
    }


def _a11y_path_from_artifacts(artifacts: Optional[dict[str, Any]]) -> Any:
    return artifacts.get("a11y_path") if artifacts else None


def _verification_item_for_ambiguity(
    *,
    step_id: int,
    function_call_index: int,
    ambiguity_candidate: AmbiguityCandidate,
    artifacts: Optional[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": f"ambiguity-step-{step_id}-{function_call_index}",
        "message": ambiguity_candidate.message,
        "detail": f"Review evidence: {', '.join(ambiguity_candidate.review_evidence)}",
        "source_step_id": step_id,
        "status": "needs_review",
        "a11y_path": _a11y_path_from_artifacts(artifacts),
        **_ambiguity_fields(ambiguity_candidate),
    }


class ActionReviewService:
    def __init__(
        self,
        query: str,
        step_summarizer: ActionStepSummarizerProtocol | None = None,
    ):
        self._query = query
        self._action_review_history: list[ActionReviewContext] = []
        self._step_summarizer = step_summarizer
        self._step_summary_cache: dict[tuple[int, int], ActionStepSummary] = {}

    def build_final_result_summary(
        self,
        *,
        final_response: str | None,
        current_url: str | None,
    ) -> str | None:
        fallback_summary = self.clean_reasoning_text(final_response)
        if self._step_summarizer is None:
            return fallback_summary

        summarized = self._step_summarizer.summarize_final_result(
            query=self._query,
            final_response=final_response,
            current_url=current_url,
        )
        return summarized or fallback_summary

    def build_action_summary(self, function_call: types.FunctionCall) -> str:
        return build_action_summary(function_call)

    def build_fallback_reason(self, function_call: types.FunctionCall) -> str:
        return build_fallback_reason(function_call)

    def clean_reasoning_text(self, reasoning: Optional[str]) -> Optional[str]:
        if not reasoning:
            return None
        cleaned_reasoning = " ".join(reasoning.split())
        return cleaned_reasoning or None

    def build_phase_metadata(
        self,
        function_call: types.FunctionCall | None,
        reasoning: Optional[str],
        step_id: int,
        *,
        final_result_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        if final_result_summary is not None or function_call is None:
            return {
                "phase_id": "phase-complete",
                "phase_label": "완료",
                "phase_summary": reasoning,
                "user_visible_label": "결과 정리",
            }

        action_name = function_call.name or "action"
        phase_id, phase_label = PHASE_GROUPS.get(action_name, DEFAULT_PHASE)

        return {
            "phase_id": phase_id,
            "phase_label": phase_label,
            "phase_summary": reasoning,
            "user_visible_label": self.build_action_summary(function_call)
            if function_call.name
            else f"Step {step_id}",
        }

    def _build_fallback_outcome(
        self,
        function_call: types.FunctionCall,
        current_url: str | None,
        previous_url: str | None,
    ) -> str:
        if current_url and previous_url and current_url != previous_url:
            try:
                host = urlparse(current_url).hostname or current_url
            except Exception:  # noqa: BLE001
                host = current_url
            return f"페이지 이동: {host}"
        action_name = function_call.name or ""
        if action_name in NAVIGATION_ACTION_NAMES:
            return "페이지 이동 요청 완료"
        return "—"

    def _get_action_step_summary(
        self,
        *,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        current_url: str | None,
        previous_url: str | None = None,
    ) -> ActionStepSummary:
        cache_key = (step_id, function_call_index)
        cached_summary = self._step_summary_cache.get(cache_key)
        if cached_summary is not None:
            return cached_summary

        fallback_summary = ActionStepSummary(
            what=self.build_action_summary(function_call),
            why=self.clean_reasoning_text(reasoning)
            or self.build_fallback_reason(function_call),
            outcome=self._build_fallback_outcome(function_call, current_url, previous_url),
            summary_source="app_derived",
        )

        if self._step_summarizer is None:
            self._step_summary_cache[cache_key] = fallback_summary
            return fallback_summary

        summarized = self._step_summarizer.summarize_action(
            query=self._query,
            function_call=function_call,
            reasoning=reasoning,
            current_url=current_url,
            previous_url=previous_url,
        )
        resolved_summary = summarized or fallback_summary
        self._step_summary_cache[cache_key] = resolved_summary
        return resolved_summary

    def build_review_metadata_for_action(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
        subgoal_id: int | None = None,
    ) -> dict[str, Any]:
        current_url = artifacts.get("url") if artifacts else None
        previous_context_for_url = (
            self._action_review_history[-1] if self._action_review_history else None
        )
        previous_url = previous_context_for_url.current_url if previous_context_for_url else None
        action_step_summary = self._get_action_step_summary(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            current_url=current_url,
            previous_url=previous_url,
        )
        current_context = ActionReviewContext(
            action_name=function_call.name or "action",
            action_args=dict(function_call.args or {}),
            current_url=current_url,
        )
        previous_context = self._action_review_history[-1] if self._action_review_history else None
        ambiguity_candidate = detect_ambiguity_candidate(
            query=self._query,
            current_action=current_context,
            previous_action=previous_context,
        )
        self._action_review_history.append(current_context)

        review_metadata = {
            **self.build_phase_metadata(
                function_call=function_call,
                reasoning=reasoning,
                step_id=step_id,
            ),
            **_action_summary_fields(action_step_summary),
            "subgoal_id": subgoal_id,
            "user_visible_label": action_step_summary.action_summary,
            **_ambiguity_fields(ambiguity_candidate),
            "a11y_path": _a11y_path_from_artifacts(artifacts),
            "verification_items": [],
        }
        if ambiguity_candidate is None:
            return review_metadata

        review_metadata["verification_items"] = [
            _verification_item_for_ambiguity(
                step_id=step_id,
                function_call_index=function_call_index,
                ambiguity_candidate=ambiguity_candidate,
                artifacts=artifacts,
            )
        ]
        return review_metadata

    def build_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        ambiguity_candidate: AmbiguityCandidate | None = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        cleaned_reasoning = self.clean_reasoning_text(reasoning)
        action_step_summary = self._get_action_step_summary(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            current_url=artifacts.get("url") if artifacts else None,
        )
        return {
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            **_action_summary_fields(action_step_summary),
            "reasoning_text": cleaned_reasoning,
            "model_step_id": step_id,
            "function_call_index_within_step": function_call_index,
            **_ambiguity_fields(ambiguity_candidate),
            "a11y_path": _a11y_path_from_artifacts(artifacts),
        }

    def merge_step_review_metadata(
        self,
        existing_metadata: dict[str, Any],
        review_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        verification_items = existing_metadata.get("verification_items", [])
        if review_metadata.get("verification_items"):
            verification_items = verification_items + review_metadata["verification_items"]

        existing_evidence = list(existing_metadata.get("review_evidence", []))
        merged_evidence = existing_evidence + [
            evidence
            for evidence in review_metadata.get("review_evidence", [])
            if evidence not in existing_evidence
        ]

        ambiguity_flag = bool(existing_metadata.get("ambiguity_flag")) or bool(
            review_metadata.get("ambiguity_flag")
        )
        ambiguity_type = existing_metadata.get("ambiguity_type")
        ambiguity_message = existing_metadata.get("ambiguity_message")
        if review_metadata.get("ambiguity_flag"):
            ambiguity_type = review_metadata.get("ambiguity_type") or ambiguity_type
            ambiguity_message = review_metadata.get("ambiguity_message") or ambiguity_message

        return {
            "phase_id": existing_metadata.get("phase_id") or review_metadata.get("phase_id"),
            "phase_label": existing_metadata.get("phase_label") or review_metadata.get("phase_label"),
            "phase_summary": existing_metadata.get("phase_summary") or review_metadata.get("phase_summary"),
            "what": existing_metadata.get("what") or review_metadata.get("what"),
            "why": existing_metadata.get("why") or review_metadata.get("why"),
            "outcome": existing_metadata.get("outcome") or review_metadata.get("outcome"),
            "action_summary": existing_metadata.get("action_summary")
            or review_metadata.get("action_summary"),
            "reason": existing_metadata.get("reason") or review_metadata.get("reason"),
            "summary_source": existing_metadata.get("summary_source")
            or review_metadata.get("summary_source"),
            "subgoal_id": existing_metadata.get("subgoal_id")
            if existing_metadata.get("subgoal_id") is not None
            else review_metadata.get("subgoal_id"),
            "user_visible_label": existing_metadata.get("user_visible_label")
            or review_metadata.get("user_visible_label"),
            "ambiguity_flag": ambiguity_flag,
            "ambiguity_type": ambiguity_type,
            "ambiguity_message": ambiguity_message,
            "review_evidence": merged_evidence,
            "a11y_path": review_metadata.get("a11y_path")
            or existing_metadata.get("a11y_path"),
            "verification_items": verification_items,
        }

