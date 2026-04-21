import os

from google import genai

from .base import BaseProvider


class GeminiProvider(BaseProvider):
    """Unified Gemini provider.

    Behavior is identical across variants; `name` is only used for provider-role
    validation (e.g. enforcing that `grounding='text'` is paired with a
    text-capable client).
    """

    def __init__(self, client: genai.Client, name: str = "gemini_api"):
        super().__init__(client=client, name=name)

    @classmethod
    def from_env(cls, name: str = "gemini_api") -> "GeminiProvider":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set.")
        return cls(client=genai.Client(api_key=api_key), name=name)


GeminiApiProvider = GeminiProvider
