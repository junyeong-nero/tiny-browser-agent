import json
import inspect
from collections.abc import Callable
from typing import Any, Literal, get_args, get_origin

from google.genai import types


_SCHEMA_TYPE_MAP = {
    "OBJECT": "object",
    "STRING": "string",
    "INTEGER": "integer",
    "NUMBER": "number",
    "DOUBLE": "number",
    "BOOLEAN": "boolean",
    "ARRAY": "array",
}


def build_function_declaration(callable_: Callable[..., object]) -> types.FunctionDeclaration:
    name = callable_.__name__
    description = (callable_.__doc__ or "").strip()
    sig = inspect.signature(callable_)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        properties[param_name] = annotation_to_json_schema(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        params_schema["required"] = required

    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters_json_schema=params_schema,
    )


def annotation_to_json_schema(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, tuple):
        item_annotation = args[0] if args else str
        return {
            "type": "array",
            "items": annotation_to_json_schema(item_annotation),
        }

    if origin is dict:
        return {"type": "object"}

    if origin is Literal:
        enum_values = list(args)
        base_schema = _literal_base_schema(enum_values)
        base_schema["enum"] = enum_values
        return base_schema

    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is dict:
        return {"type": "object"}

    return {"type": "string"}


def _literal_base_schema(values: list[Any]) -> dict[str, str]:
    if values and all(isinstance(value, bool) for value in values):
        return {"type": "boolean"}
    if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return {"type": "integer"}
    if values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        return {"type": "number"}
    return {"type": "string"}


def declaration_to_openai_tool(declaration: types.FunctionDeclaration) -> dict[str, Any]:
    return {
        "name": declaration.name,
        "description": declaration.description or "",
        "parameters": declaration_parameters_to_json_schema(declaration),
    }


def declaration_parameters_to_json_schema(
    declaration: types.FunctionDeclaration,
) -> dict[str, Any]:
    if isinstance(declaration.parameters_json_schema, dict):
        return declaration.parameters_json_schema
    if declaration.parameters is not None:
        return schema_to_json_schema(declaration.parameters)
    return {"type": "object", "properties": {}}


def schema_to_json_schema(schema: types.Schema) -> dict[str, Any]:
    dumped = schema.model_dump(exclude_none=True)
    return _normalize_schema_value(dumped)


def _normalize_schema_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {}
        for key, child in value.items():
            if key == "type":
                normalized[key] = _normalize_schema_type(child)
            else:
                normalized[key] = _normalize_schema_value(child)
        return normalized
    if isinstance(value, list):
        return [_normalize_schema_value(item) for item in value]
    return value


def _normalize_schema_type(value: Any) -> Any:
    raw = getattr(value, "value", value)
    if isinstance(raw, str):
        return _SCHEMA_TYPE_MAP.get(raw.upper(), raw.lower())
    return raw


def contents_to_messages(contents: list[types.Content]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for content in contents:
        if not content.parts:
            continue

        role = _map_role(content.role)
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        tool_messages: list[dict[str, Any]] = []

        for index, part in enumerate(content.parts):
            if part.text:
                text_parts.append(part.text)
            elif part.inline_data:
                text_parts.append(f"[{part.inline_data.mime_type}]")
            elif part.function_call:
                tool_calls.append(_function_call_to_tool_call(part.function_call, index))
            elif part.function_response:
                tool_messages.append(_function_response_to_tool_message(part.function_response))

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": "\n".join(text_parts) or None,
                    "tool_calls": tool_calls,
                }
            )
        elif text_parts:
            messages.append({"role": role, "content": "\n".join(text_parts)})

        messages.extend(tool_messages)

    return messages


def content_to_text(content: types.Content) -> str:
    parts = []
    if not content.parts:
        return ""
    for part in content.parts:
        if part.text:
            parts.append(part.text)
        elif part.inline_data:
            parts.append(f"[{part.inline_data.mime_type}]")
        elif part.function_call:
            args_str = json.dumps(part.function_call.args or {}, default=str)
            parts.append(f"[Function call: {part.function_call.name}({args_str})]")
        elif part.function_response:
            parts.append(f"[Function response: {part.function_response.response}]")
    return "\n".join(parts)


def payload_to_response(payload: dict[str, Any]) -> types.GenerateContentResponse:
    choices = payload.get("choices") or []

    candidates = []
    for choice in choices:
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        text_content = message.get("content") or ""

        parts = []
        text = _extract_message_text(text_content)
        if text:
            parts.append(types.Part(text=text))

        for tc in tool_calls:
            func = tc.get("function", {}) or {}
            func_name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        id=tc.get("id"),
                        name=func_name,
                        args=args,
                    )
                )
            )

        finish_reason_map = {
            "stop": types.FinishReason.STOP,
            "length": types.FinishReason.MAX_TOKENS,
            "content_filter": types.FinishReason.OTHER,
            "tool_calls": types.FinishReason.STOP,
        }
        finish = choice.get("finish_reason", "stop")
        finish_reason = finish_reason_map.get(
            finish,
            types.FinishReason.FINISH_REASON_UNSPECIFIED,
        )

        candidate_content = types.Content(role="model", parts=parts) if parts else None
        candidates.append(
            types.Candidate(
                content=candidate_content,
                finish_reason=finish_reason,
            )
        )

    if not candidates:
        empty_part = types.Part(text="")
        empty_content = types.Content(role="model", parts=[empty_part])
        candidates.append(
            types.Candidate(
                content=empty_content,
                finish_reason=types.FinishReason.FINISH_REASON_UNSPECIFIED,
            )
        )

    return types.GenerateContentResponse(candidates=candidates)


def _map_role(role: str | None) -> str:
    if role == "model":
        return "assistant"
    if role in {"system", "assistant", "tool"}:
        return role
    return "user"


def _function_call_to_tool_call(
    function_call: types.FunctionCall,
    index: int,
) -> dict[str, Any]:
    tool_call_id = function_call.id or f"call_{index}"
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {
            "name": function_call.name or "",
            "arguments": json.dumps(function_call.args or {}, ensure_ascii=False),
        },
    }


def _function_response_to_tool_message(
    function_response: types.FunctionResponse,
) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": function_response.id or function_response.name or "call_0",
        "content": json.dumps(function_response.response or {}, ensure_ascii=False),
    }


def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in text_parts if part).strip()
    return ""
