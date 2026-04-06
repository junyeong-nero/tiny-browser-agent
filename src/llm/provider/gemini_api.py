import os

from google import genai

from .base import BaseProvider


class GeminiApiProvider(BaseProvider):
    def __init__(self, client: genai.Client):
        super().__init__(client=client, name="gemini_api")

    @classmethod
    def from_env(cls) -> "GeminiApiProvider":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY must be set when USE_VERTEXAI is not enabled."
            )
        return cls(client=genai.Client(api_key=api_key))
