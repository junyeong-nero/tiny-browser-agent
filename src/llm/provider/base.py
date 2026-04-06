from abc import ABC
from collections.abc import Callable
from typing import Any

from google.genai import types


class BaseProvider(ABC):
    def __init__(self, client: Any, name: str):
        self._client = client
        self.name = name

    @property
    def sdk_client(self) -> Any:
        return self._client

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        return self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    def build_function_declaration(
        self, callable_: Callable[..., object]
    ) -> types.FunctionDeclaration:
        return types.FunctionDeclaration.from_callable(
            client=self._client,
            callable=callable_,
        )
