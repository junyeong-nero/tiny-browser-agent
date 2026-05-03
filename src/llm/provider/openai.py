import os
from urllib import request  # re-exported for provider tests that patch urlopen

from .chat_completion_http import ChatCompletionsProvider
from .env_config import optional_env, parse_timeout_seconds, require_env


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
            token_limit_field="max_completion_tokens",
        )

    @classmethod
    def from_env(cls) -> "OpenAIProvider":
        api_key = require_env(
            "OPENAI_API_KEY",
            "OPENAI_API_KEY must be set when OpenAI summarization is enabled.",
        )

        return cls(
            api_key=api_key,
            base_url=optional_env("OPENAI_BASE_URL", "https://api.openai.com/v1")
            or "https://api.openai.com/v1",
            timeout_seconds=parse_timeout_seconds(),
        )
