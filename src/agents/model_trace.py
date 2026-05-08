"""Serialization helpers for UI-visible model trace events."""

from __future__ import annotations

from typing import Any


def serialize_content(content: Any) -> Any:
    if content is None:
        return None
    return {
        "role": getattr(content, "role", None),
        "parts": [
            serialize_part(part)
            for part in (getattr(content, "parts", None) or [])
        ],
    }


def serialize_part(part: Any) -> dict[str, Any]:
    item: dict[str, Any] = {}
    text = getattr(part, "text", None)
    if text is not None:
        item["text"] = text
    if getattr(part, "thought", None):
        item["thought"] = True
    function_call = getattr(part, "function_call", None)
    if function_call is not None:
        item["function_call"] = {
            "name": getattr(function_call, "name", None),
            "args": json_safe(getattr(function_call, "args", None) or {}),
        }
    function_response = getattr(part, "function_response", None)
    if function_response is not None:
        item["function_response"] = {
            "name": getattr(function_response, "name", None),
            "response": json_safe(getattr(function_response, "response", None) or {}),
        }
    inline_data = getattr(part, "inline_data", None)
    if inline_data is not None:
        item["inline_data"] = {
            "mime_type": getattr(inline_data, "mime_type", None),
            "data": "<bytes omitted>",
        }
    return item


def serialize_model_response(response: Any) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "finish_reason": str(candidate.finish_reason)
                if getattr(candidate, "finish_reason", None)
                else None,
                "content": serialize_content(getattr(candidate, "content", None)),
            }
            for candidate in (getattr(response, "candidates", None) or [])
        ],
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return "<bytes omitted>"
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump(exclude_none=True))
    return str(value)
