from __future__ import annotations

from core.types import GroundingMode


COMPUTER_USE_PROVIDER_NAMES = {"gemini_api", "gemini_computer_use"}
MULTIMODAL_CHAT_PROVIDER_NAMES = {"openai", "openrouter", "nvidia"}


def validate_grounding_provider(
    grounding: GroundingMode,
    provider_name: str,
) -> None:
    if grounding == "text" and provider_name == "gemini_computer_use":
        raise ValueError(
            "grounding='text' requires a standard text model provider, "
            f"but llm_client uses '{provider_name}'. Use LLMClient.for_text()."
        )
    if (
        grounding in ("vision", "mixed")
        and provider_name not in COMPUTER_USE_PROVIDER_NAMES
        and provider_name not in MULTIMODAL_CHAT_PROVIDER_NAMES
    ):
        raise ValueError(
            f"grounding='{grounding}' requires either a computer-use provider "
            "or an OpenAI-compatible provider that supports image inputs, "
            f"but llm_client uses '{provider_name}'."
        )

