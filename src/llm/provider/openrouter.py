import json
import os
import ssl
from collections.abc import Callable
from inspect import signature
from typing import Any
from urllib import error, request

from google.genai import types

try:
    import certifi
except ImportError:  # pragma: no cover - certifi is expected via transitive deps.
    certifi = None


class OpenRouterProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        http_referer: str | None = None,
        title: str | None = None,
        timeout_seconds: float = 15.0,
    ):
        self._api_key = api_key
        self._chat_completions_url = f"{base_url.rstrip('/')}/chat/completions"
        self._http_referer = http_referer
        self._title = title
        self._timeout_seconds = timeout_seconds
        self.name = "openrouter"
        self._client = None

    @property
    def sdk_client(self) -> None:
        return None

    @classmethod
    def from_env(cls) -> "OpenRouterProvider":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY must be set when OpenRouter summarization is enabled.")

        timeout_value = os.environ.get("ACTION_SUMMARY_TIMEOUT_SECONDS", "15")
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as exc:
            raise ValueError("ACTION_SUMMARY_TIMEOUT_SECONDS must be a number.") from exc

        return cls(
            api_key=api_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            http_referer=os.environ.get("OPENROUTER_HTTP_REFERER"),
            title=os.environ.get("OPENROUTER_TITLE"),
            timeout_seconds=timeout_seconds,
        )

    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 160,
        temperature: float = 0,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format

        http_request = request.Request(
            self._chat_completions_url,
            data=json.dumps(body).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )

        try:
            with request.urlopen(
                http_request,
                timeout=self._timeout_seconds,
                context=self._build_ssl_context(),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenRouter request failed with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return self._extract_text(payload)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._title:
            headers["X-Title"] = self._title
        return headers

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if certifi is None:
            return None
        return ssl.create_default_context(cafile=certifi.where())

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter response did not contain any choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            merged = "\n".join(part for part in text_parts if part).strip()
            if merged:
                return merged
        raise RuntimeError("OpenRouter response did not contain text content.")

    def build_function_declaration(
        self, callable_: Callable[..., object]
    ) -> types.FunctionDeclaration:
        import inspect as inspect_module

        name = callable_.__name__
        description = (callable_.__doc__ or "").strip()
        sig = signature(callable_)

        properties: dict[str, types.Schema] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.annotation is inspect_module.Parameter.empty:
                param_type = "STRING"
            elif param.annotation in (int, inspect_module.Parameter.empty):
                param_type = "INTEGER"
            elif param.annotation is float:
                param_type = "DOUBLE"
            elif param.annotation is bool:
                param_type = "BOOLEAN"
            elif param.annotation is str:
                param_type = "STRING"
            else:
                param_type = "STRING"

            properties[param_name] = types.Schema(type=param_type)
            if param.default is inspect_module.Parameter.empty:
                required.append(param_name)

        params_schema = types.Schema(
            type="OBJECT",
            properties=properties if properties else None,
            required=required if required else None,
        )

        return types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=params_schema,
        )

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        messages = self._contents_to_messages(contents)

        if config.system_instruction:
            system_text = self._content_to_text(config.system_instruction)
            messages.insert(0, {"role": "system", "content": system_text})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if config.thinking_config:
            body["thinking"] = {
                "type": "enabled",
                "thinking_bytes": config.thinking_config.include_thoughts or False,
            }

        tools = []
        if config.tools:
            for tool in config.tools:
                if tool.function_declarations:
                    for decl in tool.function_declarations:
                        func_dict = {
                            "name": decl.name,
                            "description": decl.description or "",
                            "parameters": decl.parameters.model_dump(
                                exclude_none=True
                            ) if decl.parameters else {"type": "object", "properties": {}},
                        }
                        tools.append(func_dict)
            if tools:
                body["tools"] = [{"type": "function", "function": f} for f in tools]

        http_request = request.Request(
            self._chat_completions_url,
            data=json.dumps(body, default=str).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )

        try:
            with request.urlopen(
                http_request,
                timeout=self._timeout_seconds,
                context=self._build_ssl_context(),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenRouter request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return self._payload_to_response(payload)

    def _contents_to_messages(
        self, contents: list[types.Content]
    ) -> list[dict[str, Any]]:
        messages = []
        for content in contents:
            role = content.role or "user"
            for part in content.parts:
                text = self._part_to_text(part)
                if text:
                    messages.append({"role": role, "content": text})
        return messages

    def _content_to_text(self, content: types.Content) -> str:
        parts = []
        for part in content.parts:
            text = self._part_to_text(part)
            if text:
                parts.append(text)
        return "\n".join(parts)

    def _part_to_text(self, part: types.Part) -> str:
        if part.text:
            return part.text
        if part.inline_data:
            return f"[{part.inline_data.mime_type}]"
        if part.function_call:
            args_str = json.dumps(part.function_call.args, default=str)
            return f"[Function call: {part.function_call.name}({args_str})]"
        if part.function_response:
            return f"[Function response: {part.function_response.response}]"
        return ""

    def _payload_to_response(
        self, payload: dict[str, Any]
    ) -> types.GenerateContentResponse:
        choices = payload.get("choices") or []

        candidates = []
        for choice in choices:
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            text_content = message.get("content") or ""

            parts = []

            if text_content and isinstance(text_content, str) and text_content.strip():
                parts.append(types.Part(text=text_content))

            for tc in tool_calls:
                func = tc.get("function", {}) or {}
                func_name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                parts.append(
                    types.Part(function_call=types.FunctionCall(name=func_name, args=args))
                )

            finish_reason_map = {
                "stop": types.FinishReason.STOP,
                "length": types.FinishReason.MAX_TOKENS,
                "content_filter": types.FinishReason.OTHER,
                "tool_calls": types.FinishReason.STOP,
            }
            finish = choice.get("finish_reason", "stop")
            finish_reason = finish_reason_map.get(finish, types.FinishReason.FINISH_REASON_UNSPECIFIED)

            candidate_content = types.Content(role="model", parts=parts) if parts else None

            candidate = types.Candidate(
                content=candidate_content,
                finish_reason=finish_reason,
            )
            candidates.append(candidate)

        if not candidates:
            empty_part = types.Part(text="")
            empty_content = types.Content(role="model", parts=[empty_part])
            empty_candidate = types.Candidate(
                content=empty_content,
                finish_reason=types.FinishReason.FINISH_REASON_UNSPECIFIED,
            )
            candidates.append(empty_candidate)

        return types.GenerateContentResponse(candidates=candidates)
