"""Small helpers for actor tool-call execution orchestration."""

from __future__ import annotations

from typing import Any

from google.genai import types

from agents.summarizer.agent import AmbiguityCandidate
from tools.types import ExecutedCall, build_tool_error_payload


def build_tool_execution_error_message(
    function_call: types.FunctionCall,
    exc: Exception,
) -> str:
    tool_name = function_call.name or "<missing name>"
    return f"Tool execution failed for {tool_name}: {type(exc).__name__}: {exc}"


def build_tool_execution_error_call(
    function_call: types.FunctionCall,
    exc: Exception,
) -> ExecutedCall:
    error_message = build_tool_execution_error_message(function_call, exc)
    return ExecutedCall(
        function_call=function_call,
        result=build_tool_error_payload(
            tool_name=function_call.name,
            error_type=type(exc).__name__,
            error_message=error_message,
        ),
        artifacts=None,
    )


def action_payload_with_ref_name(
    function_call: types.FunctionCall,
    ref_name: str | None,
) -> dict[str, Any]:
    action_args = dict(function_call.args or {})
    if ref_name and "ref_name" not in action_args:
        action_args["ref_name"] = ref_name
    return {
        "name": function_call.name,
        "args": action_args,
    }


def ambiguity_candidate_from_review_metadata(
    review_metadata: dict[str, Any],
) -> AmbiguityCandidate | None:
    if not (
        review_metadata.get("ambiguity_flag")
        and review_metadata.get("ambiguity_type")
        and review_metadata.get("ambiguity_message")
    ):
        return None
    return AmbiguityCandidate(
        ambiguity_type=review_metadata["ambiguity_type"],
        message=review_metadata["ambiguity_message"],
        review_evidence=list(review_metadata.get("review_evidence") or []),
    )


def build_reobserve_required_response(
    function_call: types.FunctionCall,
) -> types.FunctionResponse:
    """Return a synthetic response for stale same-turn browser actions."""
    return types.FunctionResponse(
        name=function_call.name,
        id=function_call.id,
        response={
            "status": "reobserve_required",
            "tool_name": function_call.name,
            "error_type": "ReobserveRequired",
            "error": (
                "A previous browser action in this model turn changed the page state. "
                "This tool call was not executed. Re-observe the browser state before "
                "choosing the next browser action."
            ),
        },
    )
