import json
import os
from dataclasses import dataclass
from typing import Any

from google.genai import types

from llm.provider.openrouter import OpenRouterProvider


@dataclass(frozen=True)
class ActionStepSummary:
    action_summary: str
    reason: str
    summary_source: str


class OpenRouterActionStepSummarizer:
    def __init__(
        self,
        provider: OpenRouterProvider,
        model: str,
    ):
        self._provider = provider
        self._model = model

    @classmethod
    def from_env(cls) -> "OpenRouterActionStepSummarizer | None":
        configured_provider = os.environ.get("ACTION_SUMMARY_PROVIDER", "").strip().lower()
        if not configured_provider:
            return None
        if configured_provider != "openrouter":
            raise ValueError(
                f"Unsupported ACTION_SUMMARY_PROVIDER '{configured_provider}'. Expected 'openrouter'."
            )

        model = os.environ.get("ACTION_SUMMARY_MODEL", "google/gemma-4-31b-it:free").strip()
        if not model:
            raise ValueError("ACTION_SUMMARY_MODEL must not be empty when summarization is enabled.")

        return cls(
            provider=OpenRouterProvider.from_env(),
            model=model,
        )

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
            summary_source="openrouter",
        )
