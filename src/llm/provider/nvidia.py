import os
from urllib import request  # re-exported for provider tests that patch urlopen

from .chat_completion_http import ChatCompletionsProvider
from .env_config import optional_env, parse_timeout_seconds, require_env


class NvidiaProvider(ChatCompletionsProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        thinking: bool = True,
        reasoning_effort: str = "high",
        timeout_seconds: float = 15.0,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            name="nvidia",
            error_prefix="NVIDIA",
            timeout_seconds=timeout_seconds,
            extra_body={
                "chat_template_kwargs": {
                    "thinking": thinking,
                    "reasoning_effort": reasoning_effort,
                }
            },
        )

    @classmethod
    def from_env(cls) -> "NvidiaProvider":
        api_key = require_env(
            "NVIDIA_API_KEY",
            "NVIDIA_API_KEY must be set when NVIDIA provider is enabled.",
        )

        return cls(
            api_key=api_key,
            base_url=optional_env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
            or "https://integrate.api.nvidia.com/v1",
            thinking=_parse_bool(optional_env("NVIDIA_THINKING", "true") or "true"),
            reasoning_effort=optional_env("NVIDIA_REASONING_EFFORT", "high") or "high",
            timeout_seconds=parse_timeout_seconds(),
        )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}
