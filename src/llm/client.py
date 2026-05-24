import time
from collections.abc import Callable
from typing import Literal, Protocol

import termcolor
from google.genai import types

from .provider import (
    GeminiProvider,
    NvidiaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)

ProviderName = Literal[
    "gemini",
    "gemini_api",
    "gemini_text",
    "gemini_computer_use",
    "openai",
    "openrouter",
    "nvidia",
]

ProviderFactory = Callable[
    [], "ProviderProtocol"
]

PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "gemini": lambda: GeminiProvider.from_env(),
    "gemini_api": lambda: GeminiProvider.from_env(),
    "gemini_text": lambda: GeminiProvider.from_env(name="gemini_text"),
    "gemini_computer_use": lambda: GeminiProvider.from_env(name="gemini_computer_use"),
    "openai": lambda: OpenAIProvider.from_env(),
    "openrouter": lambda: OpenRouterProvider.from_env(),
    "nvidia": lambda: NvidiaProvider.from_env(),
}


def _describe_empty_response(response: types.GenerateContentResponse) -> str:
    parts: list[str] = []
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None:
        block_reason = getattr(feedback, "block_reason", None)
        if block_reason is not None:
            parts.append(f"prompt_block_reason={block_reason}")
        block_message = getattr(feedback, "block_reason_message", None)
        if block_message:
            parts.append(f"prompt_block_message={block_message!r}")
        safety = getattr(feedback, "safety_ratings", None)
        if safety:
            parts.append(f"prompt_safety_ratings={safety}")

    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        thoughts_tokens = getattr(usage, "thoughts_token_count", None)
        parts.append(
            f"usage(prompt={prompt_tokens}, total={total_tokens}, thoughts={thoughts_tokens})"
        )

    return "; ".join(parts) if parts else "no prompt_feedback or usage metadata available"


class LLMError(Exception):
    pass


class EmptyResponseError(LLMError):
    pass


class ProviderProtocol(Protocol):
    name: str

    @property
    def sdk_client(self): ...

    def build_function_declaration(
        self, callable_: Callable[..., object]
    ) -> types.FunctionDeclaration: ...

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse: ...


class LLMClient:
    def __init__(
        self,
        provider: ProviderProtocol,
        max_retries: int = 5,
        base_delay_s: int = 1,
    ):
        self._provider = provider
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls(provider=GeminiProvider.from_env())

    @classmethod
    def from_provider_name(
        cls,
        provider_name: str,
        *,
        max_retries: int = 5,
        base_delay_s: int = 1,
    ) -> "LLMClient":
        factory = PROVIDER_FACTORIES.get(provider_name)
        if factory is None:
            raise ValueError(f"Unsupported LLM provider '{provider_name}'.")
        return cls(
            provider=factory(),
            max_retries=max_retries,
            base_delay_s=base_delay_s,
        )

    @classmethod
    def for_computer_use(cls) -> "LLMClient":
        return cls(provider=GeminiProvider.from_env(name="gemini_computer_use"))

    @classmethod
    def for_text(cls) -> "LLMClient":
        return cls(provider=GeminiProvider.from_env(name="gemini_text"))

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def sdk_client(self):
        return self._provider.sdk_client

    def build_function_declaration(
        self, callable_: Callable[..., object]
    ) -> types.FunctionDeclaration:
        return self._provider.build_function_declaration(callable_)

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._provider.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                last_error = exc
            else:
                if response.candidates:
                    return response
                diagnostics = _describe_empty_response(response)
                termcolor.cprint(
                    f"Empty response diagnostics: {diagnostics}\n",
                    color="yellow",
                )
                last_error = EmptyResponseError(
                    "Model returned no candidates after a successful request. "
                    f"{diagnostics}"
                )

            if attempt < self._max_retries - 1:
                delay = self._base_delay_s * (2**attempt)
                termcolor.cprint(
                    (
                        f"Generating content failed on attempt {attempt + 1}. "
                        f"Retrying in {delay} seconds...\n"
                    ),
                    color="yellow",
                )
                time.sleep(delay)

        termcolor.cprint(
            f"Generating content failed after {self._max_retries} attempts.\n",
            color="red",
        )
        if last_error is None:
            raise LLMError("Generating content failed for an unknown reason.")
        raise last_error
