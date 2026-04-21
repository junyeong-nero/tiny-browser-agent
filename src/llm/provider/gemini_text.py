from .gemini_api import GeminiProvider


class GeminiTextProvider(GeminiProvider):
    @classmethod
    def from_env(cls, name: str = "gemini_text") -> "GeminiTextProvider":
        return super().from_env(name=name)  # type: ignore[return-value]
