import os
from urllib import request  # re-exported for provider tests that patch urlopen

from .chat_completion_http import ChatCompletionsProvider


class OpenRouterProvider(ChatCompletionsProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        http_referer: str | None = None,
        title: str | None = None,
        timeout_seconds: float = 15.0,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            name="openrouter",
            error_prefix="OpenRouter",
            timeout_seconds=timeout_seconds,
        )
        self._http_referer = http_referer
        self._title = title

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

    def _build_headers(self) -> dict[str, str]:
        headers = super()._build_headers()
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._title:
            headers["X-Title"] = self._title
        return headers
