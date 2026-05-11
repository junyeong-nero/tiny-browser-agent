from .chat_completion_http import ChatCompletionsProvider
from .env_config import optional_env, parse_timeout_seconds, require_env


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
        api_key = require_env(
            "OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY must be set when OpenRouter summarization is enabled.",
        )

        return cls(
            api_key=api_key,
            base_url=optional_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            or "https://openrouter.ai/api/v1",
            http_referer=optional_env("OPENROUTER_HTTP_REFERER"),
            title=optional_env("OPENROUTER_TITLE"),
            timeout_seconds=parse_timeout_seconds(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = super()._build_headers()
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._title:
            headers["X-Title"] = self._title
        return headers
