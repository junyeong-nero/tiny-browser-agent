import json
import inspect
import base64
from collections.abc import Callable
from typing import Any, Literal, get_args, get_origin

from google.genai import types

from tools.types import TOOL_ARGUMENT_ERROR_KEY, build_tool_argument_parse_error


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


def _literal_base_schema(values: list[Any]) -> dict[str, Any]:
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
        image_parts: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        tool_messages: list[dict[str, Any]] = []
        post_tool_observations: list[dict[str, Any]] = []

        for index, part in enumerate(content.parts):
            if part.text:
                text_parts.append(part.text)
            elif part.inline_data:
                image_content = _inline_data_to_image_content(part.inline_data)
                if image_content is None:
                    text_parts.append(f"[{part.inline_data.mime_type}]")
                else:
                    image_parts.append(image_content)
            elif part.function_call:
                tool_calls.append(_function_call_to_tool_call(part.function_call, index))
            elif part.function_response:
                tool_messages.append(_function_response_to_tool_message(part.function_response))
                observation = _function_response_to_image_observation(part.function_response)
                if observation is not None:
                    post_tool_observations.append(observation)

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": "\n".join(text_parts) or None,
                    "tool_calls": tool_calls,
                }
            )
        elif text_parts or image_parts:
            messages.append({"role": role, "content": _content_payload(text_parts, image_parts)})

        messages.extend(tool_messages)
        messages.extend(post_tool_observations)

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
        reasoning_text = _extract_reasoning_text(message)
        if reasoning_text:
            parts.append(types.Part(text=reasoning_text, thought=True))

        text = _extract_message_text(text_content)
        if text:
            parts.append(types.Part(text=text))

        for tool_call_index, tc in enumerate(tool_calls):
            func = tc.get("function", {}) or {}
            func_name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError as exc:
                args = {
                    TOOL_ARGUMENT_ERROR_KEY: build_tool_argument_parse_error(
                        tool_name=func_name,
                        raw_arguments=args_str,
                        exc=exc,
                    )
                }
            tool_call_id = tc.get("id") or f"call_{tool_call_index}"
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        id=tool_call_id,
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


def _function_response_to_image_observation(
    function_response: types.FunctionResponse,
) -> dict[str, Any] | None:
    image_parts = []
    for response_part in function_response.parts or []:
        inline_data = getattr(response_part, "inline_data", None)
        if inline_data is None:
            continue
        image_content = _inline_data_to_image_content(inline_data)
        if image_content is not None:
            image_parts.append(image_content)
    if not image_parts:
        return None
    name = function_response.name or "browser tool"
    return {
        "role": "user",
        "content": _content_payload(
            [f"Screenshot observation returned after `{name}`."],
            image_parts,
        ),
    }


def _content_payload(
    text_parts: list[str],
    image_parts: list[dict[str, Any]],
) -> str | list[dict[str, Any]]:
    text = "\n".join(part for part in text_parts if part).strip()
    if not image_parts:
        return text
    payload: list[dict[str, Any]] = []
    if text:
        payload.append({"type": "text", "text": text})
    payload.extend(image_parts)
    return payload


def _inline_data_to_image_content(inline_data: Any) -> dict[str, Any] | None:
    mime_type = getattr(inline_data, "mime_type", None) or "image/png"
    if mime_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        return None
    raw_data = getattr(inline_data, "data", None)
    if isinstance(raw_data, str):
        encoded = raw_data
    elif isinstance(raw_data, bytes):
        encoded = base64.b64encode(raw_data).decode("ascii")
    else:
        return None
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{encoded}",
        },
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


def _extract_reasoning_text(message: dict[str, Any]) -> str:
    for key in ("reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
