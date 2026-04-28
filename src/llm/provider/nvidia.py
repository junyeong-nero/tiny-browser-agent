import os
from urllib import request  # re-exported for provider tests that patch urlopen

from .chat_completion_http import ChatCompletionsProvider


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
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY must be set when NVIDIA provider is enabled.")

        timeout_value = os.environ.get("ACTION_SUMMARY_TIMEOUT_SECONDS", "15")
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as exc:
            raise ValueError("ACTION_SUMMARY_TIMEOUT_SECONDS must be a number.") from exc

        return cls(
            api_key=api_key,
            base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            thinking=_parse_bool(os.environ.get("NVIDIA_THINKING", "true")),
            reasoning_effort=os.environ.get("NVIDIA_REASONING_EFFORT", "high"),
            timeout_seconds=timeout_seconds,
        )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}
