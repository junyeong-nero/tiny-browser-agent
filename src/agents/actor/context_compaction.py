"""Deterministic trajectory compaction for actor model requests."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from google.genai import types

SUMMARY_PREFIX = "Compacted trajectory summary:"
_TEXT_LIMIT = 240
_VALUE_LIMIT = 120
_MAX_RESPONSE_KEYS = 8


def build_effective_contents(
    full_contents: list[types.Content],
    query: str,
    current_subgoal_id: int | None = None,
    recent_turn_limit: int = 8,
    compact_after: int = 16,
) -> list[types.Content]:
    """Return model-facing contents while preserving the full input history.

    Short trajectories are returned unchanged. For long trajectories, keep the
    original task content, summarize older trajectory turns deterministically,
    and append recent complete tool-call/tool-response units without mutating
    ``full_contents``.
    """
    if len(full_contents) <= compact_after:
        return full_contents
    if not full_contents:
        return []

    first_content = full_contents[0]
    trailing_contents = full_contents[1:]
    old_contents, recent_contents = _split_old_and_recent_complete_units(
        trailing_contents,
        recent_turn_limit,
    )
    summary = summarize_old_contents(
        old_contents,
        query=query,
        current_subgoal_id=current_subgoal_id,
        omitted_turn_count=len(old_contents),
    )
    return [
        first_content,
        types.Content(role="user", parts=[types.Part(text=summary)]),
        *recent_contents,
    ]


def summarize_old_contents(
    old_contents: Iterable[types.Content],
    *,
    query: str | None = None,
    current_subgoal_id: int | None = None,
    omitted_turn_count: int | None = None,
) -> str:
    """Build a compact, deterministic text summary without calling an LLM."""
    contents = list(old_contents)
    lines = [SUMMARY_PREFIX]
    if query:
        lines.append(f"Original user task: {_truncate(query, _TEXT_LIMIT)}")
    if current_subgoal_id is not None:
        lines.append(f"Current subgoal: id={current_subgoal_id} status=active")
    turn_count = len(contents) if omitted_turn_count is None else omitted_turn_count
    lines.append(f"Omitted older content turns: {turn_count}")

    last_known_url = _last_known_url(contents)
    if last_known_url:
        lines.append(f"Last known URL: {last_known_url}")

    completed_actions: list[str] = []
    failed_actions: list[str] = []
    observations: list[str] = []
    other_turns: list[str] = []

    for content in contents:
        part_summaries = _summarize_content_parts(content)
        if not part_summaries:
            continue
        for part_summary in part_summaries:
            if part_summary.startswith("tool_response:"):
                response_summary = part_summary.removeprefix("tool_response: ")
                if _looks_failed_response(part_summary):
                    failed_actions.append(response_summary)
                else:
                    completed_actions.append(response_summary)
                observations.append(response_summary)
            elif part_summary.startswith("tool_call:"):
                other_turns.append(part_summary.removeprefix("tool_call: "))
            else:
                other_turns.append(part_summary)

    _append_section(lines, "Completed actions", completed_actions)
    _append_section(lines, "Failed or retried actions", failed_actions)
    _append_section(lines, "Important observations", observations)
    _append_section(lines, "Other older turns", other_turns)
    return "\n".join(lines)


def _split_old_and_recent_complete_units(
    contents: list[types.Content],
    recent_turn_limit: int,
) -> tuple[list[types.Content], list[types.Content]]:
    if recent_turn_limit <= 0:
        return contents, []

    units: list[list[types.Content]] = []
    index = 0
    while index < len(contents):
        content = contents[index]
        if (
            _has_function_call(content)
            and index + 1 < len(contents)
            and _has_function_response(contents[index + 1])
        ):
            units.append([content, contents[index + 1]])
            index += 2
            continue
        units.append([content])
        index += 1

    recent_units: list[list[types.Content]] = []
    recent_count = 0
    for unit in reversed(units):
        if recent_count >= recent_turn_limit:
            break
        recent_units.insert(0, unit)
        recent_count += len(unit)

    recent_contents = [content for unit in recent_units for content in unit]
    old_count = len(contents) - len(recent_contents)
    return contents[:old_count], recent_contents


def _summarize_content_parts(content: types.Content) -> list[str]:
    summaries: list[str] = []
    for part in content.parts or []:
        if part.text:
            summaries.append(
                f"{content.role or 'unknown'} text: {_truncate(part.text, _TEXT_LIMIT)}"
            )
        if part.function_call:
            summaries.append(f"tool_call: {_summarize_function_call(part.function_call)}")
        if part.function_response:
            summaries.append(
                f"tool_response: {_summarize_function_response(part.function_response)}"
            )
    return summaries


def _summarize_function_call(function_call: types.FunctionCall) -> str:
    name = function_call.name or "<unknown>"
    args = _summarize_mapping(function_call.args or {})
    return f"{name}({args})"


def _summarize_function_response(function_response: types.FunctionResponse) -> str:
    name = function_response.name or "<unknown>"
    response = function_response.response or {}
    fields: list[str] = []
    if isinstance(response, dict):
        for key in ("url", "error", "result", "status", "message"):
            if key in response and response[key] is not None:
                fields.append(f"{key}={_summarize_value(response[key])}")
        if "aria_snapshot" in response:
            fields.append("has_aria=true")
        for key in list(response.keys())[:_MAX_RESPONSE_KEYS]:
            if key in {
                "url",
                "error",
                "result",
                "status",
                "message",
                "aria_snapshot",
            }:
                continue
            fields.append(f"{key}={_summarize_value(response[key])}")
    else:
        fields.append(f"response={_summarize_value(response)}")
    if _has_inline_data(function_response.parts):
        fields.append("has_screenshot=true")
    return f"{name}: " + ", ".join(fields) if fields else name


def _summarize_mapping(mapping: dict[str, Any]) -> str:
    if not mapping:
        return ""
    pieces = [f"{key}={_summarize_value(mapping[key])}" for key in sorted(mapping.keys())]
    return ", ".join(pieces)


def _summarize_value(value: Any) -> str:
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, str):
        return _truncate(value, _VALUE_LIMIT)
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        encoded = str(value)
    return _truncate(encoded, _VALUE_LIMIT)


def _last_known_url(contents: Iterable[types.Content]) -> str | None:
    last_url: str | None = None
    for content in contents:
        for part in content.parts or []:
            function_response = part.function_response
            response = function_response.response if function_response else None
            if isinstance(response, dict) and isinstance(response.get("url"), str):
                last_url = response["url"]
    return last_url


def _looks_failed_response(summary: str) -> bool:
    lowered = summary.lower()
    return (
        "error=" in lowered
        or "status=\"error\"" in lowered
        or "status=error" in lowered
    )


def _append_section(
    lines: list[str],
    title: str,
    items: list[str],
    *,
    limit: int = 12,
) -> None:
    if not items:
        return
    lines.append(f"{title}:")
    for item in items[-limit:]:
        lines.append(f"- {item}")


def _has_function_call(content: types.Content) -> bool:
    return any(part.function_call for part in content.parts or [])


def _has_function_response(content: types.Content) -> bool:
    return any(part.function_response for part in content.parts or [])


def _has_inline_data(parts: list[types.FunctionResponsePart] | None) -> bool:
    return any(part.inline_data is not None for part in parts or [])


def _truncate(text: str, limit: int) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 1)]}…"
