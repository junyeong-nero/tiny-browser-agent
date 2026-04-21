from .gemini_api import GeminiProvider


class GeminiComputerUseProvider(GeminiProvider):
    @classmethod
    def from_env(cls, name: str = "gemini_computer_use") -> "GeminiComputerUseProvider":
        return super().from_env(name=name)  # type: ignore[return-value]
