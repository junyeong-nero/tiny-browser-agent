"""Small helpers for parsing and retry-classifying actor model turns."""

from __future__ import annotations

from typing import Optional

from google.genai import types
from google.genai.types import Candidate, Content, FinishReason


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporarily_unavailable",
    "service unavailable",
    "unavailable",
    "internal error",
    "deadline exceeded",
    "rate limit",
    "resource_exhausted",
    "resource exhausted",
    "connection reset",
    "connection aborted",
    "connection error",
    "broken pipe",
    "retry",
)


def should_retry_model_request(error: Exception) -> bool:
    """Return whether a provider error is likely transient."""
    status_code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if isinstance(status_code, int) and status_code in RETRYABLE_STATUS_CODES:
        return True
    message = str(error).lower()
    return any(marker in message for marker in RETRYABLE_ERROR_MARKERS)


def collect_text(candidate: Candidate, *, include_thoughts: bool) -> Optional[str]:
    """Collect text parts from a model candidate."""
    if not candidate.content or not candidate.content.parts:
        return None
    text = [
        part.text
        for part in candidate.content.parts
        if part.text and (include_thoughts or not getattr(part, "thought", False))
    ]
    return " ".join(text) or None


def strip_thought_parts(content: Content) -> Content:
    """Return a content copy that omits non-portable thought parts."""
    if not content.parts:
        return content
    filtered = [part for part in content.parts if not getattr(part, "thought", False)]
    if len(filtered) == len(content.parts):
        return content
    return Content(role=content.role, parts=filtered)


def extract_function_calls(candidate: Candidate) -> list[types.FunctionCall]:
    """Extract function calls from a model candidate."""
    if not candidate.content or not candidate.content.parts:
        return []
    return [part.function_call for part in candidate.content.parts if part.function_call]


def is_malformed_function_call_turn(
    candidate: Candidate,
    *,
    reasoning: Optional[str],
    function_calls: list[types.FunctionCall],
) -> bool:
    return (
        not function_calls
        and not reasoning
        and candidate.finish_reason == FinishReason.MALFORMED_FUNCTION_CALL
    )
