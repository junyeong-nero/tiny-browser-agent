from dataclasses import dataclass
from typing import Any, Optional

from google.genai import types


NAVIGATION_ACTION_NAMES = {
    "navigate",
    "search",
    "go_back",
    "go_forward",
    "open_web_browser",
}


@dataclass(frozen=True)
class ActionReviewContext:
    action_name: str
    action_args: dict[str, Any]
    current_url: str | None


@dataclass(frozen=True)
class AmbiguityCandidate:
    ambiguity_type: str
    message: str
    review_evidence: list[str]


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def detect_ambiguity_candidate(
    *,
    query: str,
    current_action: ActionReviewContext,
    previous_action: ActionReviewContext | None,
) -> AmbiguityCandidate | None:
    if current_action.action_name == "type_text_at":
        typed_text = current_action.action_args.get("text")
        if isinstance(typed_text, str):
            normalized_typed_text = _normalize_text(typed_text)
            if len(normalized_typed_text) >= 3 and normalized_typed_text not in _normalize_text(
                query
            ):
                return AmbiguityCandidate(
                    ambiguity_type="typed_text_not_in_query",
                    message="Entered text was not explicitly present in the original request.",
                    review_evidence=["typed_text_not_in_query"],
                )

    if (
        previous_action is not None
        and current_action.action_name in {"click_at", "type_text_at"}
        and current_action.action_name == previous_action.action_name
        and current_action.current_url == previous_action.current_url
        and current_action.action_args == previous_action.action_args
    ):
        evidence = (
            "repeated_click_pattern"
            if current_action.action_name == "click_at"
            else "repeated_type_pattern"
        )
        return AmbiguityCandidate(
            ambiguity_type=evidence,
            message="Repeated interaction was detected on the same page without new context.",
            review_evidence=[evidence],
        )

    if (
        previous_action is not None
        and previous_action.current_url
        and current_action.current_url
        and previous_action.current_url != current_action.current_url
        and current_action.action_name not in NAVIGATION_ACTION_NAMES
    ):
        return AmbiguityCandidate(
            ambiguity_type="url_changed_without_navigate",
            message="The page URL changed without an explicit navigation action.",
            review_evidence=["url_changed_without_navigate"],
        )

    return None


class ActionReviewService:
    def __init__(self, query: str):
        self._query = query
        self._action_review_history: list[ActionReviewContext] = []

    def build_action_summary(self, function_call: types.FunctionCall) -> str:
        action_name = function_call.name or "action"
        action_args = dict(function_call.args or {})

        if action_name == "open_web_browser":
            return "Opened the web browser"
        if action_name == "click_at":
            return f"Clicked at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "hover_at":
            return f"Hovered at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "type_text_at":
            return f"Typed text at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "scroll_document":
            return f"Scrolled the document {action_args.get('direction')}"
        if action_name == "scroll_at":
            return (
                f"Scrolled {action_args.get('direction')} at "
                f"({action_args.get('x')}, {action_args.get('y')})"
            )
        if action_name == "wait_5_seconds":
            return "Waited for 5 seconds"
        if action_name == "go_back":
            return "Went back to the previous page"
        if action_name == "go_forward":
            return "Went forward to the next page"
        if action_name == "search":
            return "Opened the search page"
        if action_name == "navigate":
            return f"Navigated to {action_args.get('url')}"
        if action_name == "key_combination":
            return f"Pressed key combination {action_args.get('keys')}"
        if action_name == "drag_and_drop":
            return (
                f"Dragged from ({action_args.get('x')}, {action_args.get('y')}) to "
                f"({action_args.get('destination_x')}, {action_args.get('destination_y')})"
            )
        return f"Executed {action_name}"

    def build_fallback_reason(self, function_call: types.FunctionCall) -> str:
        action_name = function_call.name or "action"
        action_args = dict(function_call.args or {})

        if action_name == "navigate":
            return f"Needed to open {action_args.get('url')}."
        if action_name == "click_at":
            return "Needed to click the selected page location."
        if action_name == "hover_at":
            return "Needed to inspect the selected page location."
        if action_name == "type_text_at":
            return "Needed to enter text into the page."
        if action_name in {"scroll_document", "scroll_at"}:
            return "Needed to move the page view to continue."
        if action_name == "wait_5_seconds":
            return "Needed to wait for the page state to settle."
        if action_name == "go_back":
            return "Needed to return to the previous page."
        if action_name == "go_forward":
            return "Needed to move forward in browser history."
        if action_name == "search":
            return "Needed to open the search page."
        if action_name == "key_combination":
            return "Needed to trigger a keyboard shortcut."
        if action_name == "drag_and_drop":
            return "Needed to move an on-page element."
        return f"Needed to execute {action_name}."

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
        if action_name in {"open_web_browser", "search", "navigate", "go_back", "go_forward"}:
            phase_id = "phase-navigation"
            phase_label = "페이지 이동"
        elif action_name in {"click_at", "hover_at"}:
            phase_id = "phase-interaction"
            phase_label = "페이지 상호작용"
        elif action_name in {"type_text_at", "key_combination", "drag_and_drop"}:
            phase_id = "phase-input"
            phase_label = "입력 및 조작"
        else:
            phase_id = "phase-observation"
            phase_label = "페이지 확인"

        return {
            "phase_id": phase_id,
            "phase_label": phase_label,
            "phase_summary": reasoning,
            "user_visible_label": self.build_action_summary(function_call)
            if function_call.name
            else f"Step {step_id}",
        }

    def build_review_metadata_for_action(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        current_context = ActionReviewContext(
            action_name=function_call.name or "action",
            action_args=dict(function_call.args or {}),
            current_url=artifacts.get("url") if artifacts else None,
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
            "ambiguity_flag": ambiguity_candidate is not None,
            "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
            "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
            "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
            "a11y_path": artifacts.get("a11y_path") if artifacts else None,
            "verification_items": [],
        }
        if ambiguity_candidate is None:
            return review_metadata

        review_metadata["verification_items"] = [
            {
                "id": f"ambiguity-step-{step_id}-{function_call_index}",
                "message": ambiguity_candidate.message,
                "detail": f"Review evidence: {', '.join(ambiguity_candidate.review_evidence)}",
                "source_step_id": step_id,
                "status": "needs_review",
                "a11y_path": artifacts.get("a11y_path") if artifacts else None,
                "ambiguity_flag": True,
                "ambiguity_type": ambiguity_candidate.ambiguity_type,
                "ambiguity_message": ambiguity_candidate.message,
                "review_evidence": ambiguity_candidate.review_evidence,
            }
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
        return {
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            "action_summary": self.build_action_summary(function_call),
            "reason": cleaned_reasoning or self.build_fallback_reason(function_call),
            "reasoning_text": cleaned_reasoning,
            "summary_source": "app_derived",
            "model_step_id": step_id,
            "function_call_index_within_step": function_call_index,
            "ambiguity_flag": ambiguity_candidate is not None,
            "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
            "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
            "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
            "a11y_path": artifacts.get("a11y_path") if artifacts else None,
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
