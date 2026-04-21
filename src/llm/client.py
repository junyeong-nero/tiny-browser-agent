import time
from collections.abc import Callable

import termcolor
from google.genai import types

from .provider import BaseProvider, GeminiApiProvider, GeminiComputerUseProvider, GeminiTextProvider


class LLMError(Exception):
    pass


class EmptyResponseError(LLMError):
    pass


class LLMClient:
    def __init__(
        self,
        provider: BaseProvider,
        max_retries: int = 5,
        base_delay_s: int = 1,
    ):
        self._provider = provider
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls(provider=GeminiApiProvider.from_env())

    @classmethod
    def for_computer_use(cls) -> "LLMClient":
        """Client for computer-use models (e.g. actor agent)."""
        return cls(provider=GeminiComputerUseProvider.from_env())

    @classmethod
    def for_text(cls) -> "LLMClient":
        """Client for standard text/structured-output models (e.g. planner, summary)."""
        return cls(provider=GeminiTextProvider.from_env())

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
                last_error = EmptyResponseError(
                    "Model returned no candidates after a successful request."
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
