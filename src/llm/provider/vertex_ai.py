import os

from google import genai

from .base import BaseProvider


class VertexAIProvider(BaseProvider):
    def __init__(self, client: genai.Client):
        super().__init__(client=client, name="vertex_ai")

    @classmethod
    def from_env(cls) -> "VertexAIProvider":
        project = os.environ.get("VERTEXAI_PROJECT")
        location = os.environ.get("VERTEXAI_LOCATION")

        if not project:
            raise ValueError(
                "VERTEXAI_PROJECT must be set when USE_VERTEXAI is enabled."
            )
        if not location:
            raise ValueError(
                "VERTEXAI_LOCATION must be set when USE_VERTEXAI is enabled."
            )

        return cls(
            client=genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )
        )
