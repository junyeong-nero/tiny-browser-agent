from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .formatters import NAVIGATION_ACTION_NAMES


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
        and current_action.action_name in {"click_at", "click_by_ref", "type_text_at"}
        and current_action.action_name == previous_action.action_name
        and current_action.current_url == previous_action.current_url
        and current_action.action_args == previous_action.action_args
    ):
        evidence = (
            "repeated_click_pattern"
            if current_action.action_name in {"click_at", "click_by_ref"}
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

