import json
import ssl
from collections.abc import Callable
from typing import Any
from urllib import error, request

from google.genai import types

from .chat_completion_adapter import (
    build_function_declaration as build_chat_function_declaration,
    content_to_text,
    contents_to_messages,
    declaration_to_openai_tool,
    payload_to_response,
)

try:
    import certifi
except ImportError:  # pragma: no cover - certifi is expected via transitive deps.
    certifi = None


class ChatCompletionsProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        name: str,
        error_prefix: str,
        timeout_seconds: float = 15.0,
    ):
        self._api_key = api_key
        self._chat_completions_url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout_seconds = timeout_seconds
        self.name = name
        self._error_prefix = error_prefix
        self._client = None

    @property
    def sdk_client(self) -> None:
        return None

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
        body = self._build_text_body(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        payload = self._post_json(body)
        return self._extract_text(payload)

    def build_function_declaration(
        self, callable_: Callable[..., object]
    ) -> types.FunctionDeclaration:
        return build_chat_function_declaration(callable_)

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        body = self._build_content_body(model=model, contents=contents, config=config)
        payload = self._post_json(body)
        return payload_to_response(payload)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_text_body(
        self,
        *,
        model: str,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
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
        return body

    def _build_content_body(
        self,
        *,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> dict[str, Any]:
        messages = contents_to_messages(contents)

        if config.system_instruction:
            system_text = content_to_text(config.system_instruction)
            messages.insert(0, {"role": "system", "content": system_text})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        tools = []
        if config.tools:
            for tool in config.tools:
                if tool.function_declarations:
                    for decl in tool.function_declarations:
                        tools.append(declaration_to_openai_tool(decl))
            if tools:
                body["tools"] = [{"type": "function", "function": f} for f in tools]
        return body

    def _post_json(self, body: dict[str, Any]) -> dict[str, Any]:
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
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{self._error_prefix} request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"{self._error_prefix} request failed: {exc.reason}") from exc

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if certifi is None:
            return None
        return ssl.create_default_context(cafile=certifi.where())

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self._error_prefix} response did not contain any choices.")

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
        raise RuntimeError(f"{self._error_prefix} response did not contain text content.")
