import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

from llm.provider.openai import OpenAIProvider
from llm.provider.openrouter import OpenRouterProvider


@dataclass(frozen=True)
class ActionStepSummary:
    action_summary: str
    reason: str
    summary_source: str


class ActionSummaryTextProvider(Protocol):
    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 160,
        temperature: float = 0,
        response_format: dict[str, Any] | None = None,
    ) -> str: ...


class ActionStepSummarizerProtocol(Protocol):
    def summarize_action(
        self,
        *,
        query: str,
        function_call: types.FunctionCall,
        reasoning: str | None,
        current_url: str | None,
    ) -> ActionStepSummary | None: ...

    def summarize_final_result(
        self,
        *,
        query: str,
        final_response: str | None,
        current_url: str | None,
    ) -> str | None: ...


class ActionStepSummarizer:
    def __init__(
        self,
        provider: ActionSummaryTextProvider,
        model: str,
        summary_source: str,
    ):
        self._provider = provider
        self._model = model
        self._summary_source = summary_source

    @classmethod
    def from_env(cls) -> "ActionStepSummarizer | None":
        configured_provider = cls._resolve_provider_from_env()
        if not configured_provider:
            return None
        if configured_provider not in {"openai", "openrouter"}:
            raise ValueError(
                f"Unsupported ACTION_SUMMARY_PROVIDER '{configured_provider}'. Expected 'openai' or 'openrouter'."
            )

        model = os.environ.get("ACTION_SUMMARY_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise ValueError("ACTION_SUMMARY_MODEL must not be empty when summarization is enabled.")

        provider = (
            OpenAIProvider.from_env()
            if configured_provider == "openai"
            else OpenRouterProvider.from_env()
        )

        return cls(
            provider=provider,
            model=model,
            summary_source=configured_provider,
        )

    @staticmethod
    def _resolve_provider_from_env() -> str:
        configured_provider = os.environ.get("ACTION_SUMMARY_PROVIDER", "").strip().lower()
        if configured_provider:
            return configured_provider
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return "openai"
        if os.environ.get("OPENROUTER_API_KEY", "").strip():
            return "openrouter"
        return ""

    def summarize_action(
        self,
        *,
        query: str,
        function_call: types.FunctionCall,
        reasoning: str | None,
        current_url: str | None,
    ) -> ActionStepSummary | None:
        prompt_payload = {
            "user_request": query,
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            "model_reasoning": reasoning,
            "current_url": current_url,
        }

        try:
            raw_response = self._provider.generate_text(
                model=self._model,
                system_prompt=(
                    "You summarize browser automation action steps for end users. "
                    "Return strict JSON only. "
                    "Never invent unseen page details. "
                    "Write concise Korean text."
                ),
                prompt=(
                    "Summarize the executed browser action.\n"
                    "Return JSON with keys action_summary and reason.\n"
                    "- action_summary: a short Korean label for the executed step.\n"
                    "- reason: one Korean sentence explaining why the step was needed.\n"
                    "If the reason is unclear, infer conservatively from the request and action only.\n\n"
                    f"{json.dumps(prompt_payload, ensure_ascii=False)}"
                ),
                max_tokens=160,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "action_step_summary",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "action_summary": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["action_summary", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
        except Exception:
            return None

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return None

        action_summary = parsed.get("action_summary")
        reason = parsed.get("reason")
        if not isinstance(action_summary, str) or not action_summary.strip():
            return None
        if not isinstance(reason, str) or not reason.strip():
            return None

        return ActionStepSummary(
            action_summary=" ".join(action_summary.split()),
            reason=" ".join(reason.split()),
            summary_source=self._summary_source,
        )

    def summarize_final_result(
        self,
        *,
        query: str,
        final_response: str | None,
        current_url: str | None,
    ) -> str | None:
        prompt_payload = {
            "user_request": query,
            "model_final_response": final_response,
            "current_url": current_url,
        }

        try:
            raw_response = self._provider.generate_text(
                model=self._model,
                system_prompt=(
                    "You rewrite the browser agent's final outcome for end users. "
                    "Return strict JSON only. "
                    "Never mention internal deliberation, screenshots, waiting, or that you are an agent unless the user explicitly asked for that. "
                    "Answer the user's request directly in concise Korean."
                ),
                prompt=(
                    "Rewrite the final browser task outcome as the answer shown in chat.\n"
                    "Return JSON with key final_result_summary.\n"
                    "- final_result_summary: one concise Korean answer for the user's request.\n"
                    "Do not narrate the browser process.\n"
                    "If the model response is vague, infer conservatively from the request and visible result only.\n\n"
                    f"{json.dumps(prompt_payload, ensure_ascii=False)}"
                ),
                max_tokens=120,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "final_result_summary",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "final_result_summary": {"type": "string"},
                            },
                            "required": ["final_result_summary"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
        except Exception:
            return None

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return None

        final_result_summary = parsed.get("final_result_summary")
        if not isinstance(final_result_summary, str) or not final_result_summary.strip():
            return None

        return " ".join(final_result_summary.split())
