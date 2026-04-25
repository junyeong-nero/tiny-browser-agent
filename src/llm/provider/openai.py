import os
from urllib import request  # re-exported for provider tests that patch urlopen

from .chat_completion_http import ChatCompletionsProvider


class OpenAIProvider(ChatCompletionsProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 15.0,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            name="openai",
            error_prefix="OpenAI",
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def from_env(cls) -> "OpenAIProvider":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set when OpenAI summarization is enabled.")

        timeout_value = os.environ.get("ACTION_SUMMARY_TIMEOUT_SECONDS", "15")
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as exc:
            raise ValueError("ACTION_SUMMARY_TIMEOUT_SECONDS must be a number.") from exc

        return cls(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=timeout_seconds,
        )
