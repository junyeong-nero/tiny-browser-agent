from __future__ import annotations

import json
import os
import re

from google.genai import types

import config as app_config
from llm.provider.nvidia import NvidiaProvider
from llm.provider.openai import OpenAIProvider
from llm.provider.openrouter import OpenRouterProvider

from .types import ActionStepSummary, ActionSummaryTextProvider


_LEAK_PATTERN = re.compile(
    r"\b(?:ARIA|snapshot|frame\s*\d*|nodes?|ref|diff)\b"
    r"|트리\s*구조"
    r"|ARIA\s*트리"
    r"|\{[^}]*\}"
    r"|^\s*[+\-]\s+\S",
    re.IGNORECASE | re.MULTILINE,
)


def _clean_summary_field(text: str, replacement: str) -> str:
    normalized = " ".join(text.split())
    return replacement if _LEAK_PATTERN.search(normalized) else normalized


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
        summary_config = app_config.summary_config()
        configured_provider = os.environ.get(
            "ACTION_SUMMARY_PROVIDER", summary_config.provider
        ).strip().lower()
        if configured_provider not in {"openai", "openrouter", "nvidia"}:
            raise ValueError(
                f"Unsupported ACTION_SUMMARY_PROVIDER '{configured_provider}'. Expected 'openai', 'openrouter', or 'nvidia'."
            )
        if not cls._provider_has_credentials(configured_provider):
            return None

        model = os.environ.get("ACTION_SUMMARY_MODEL", summary_config.model).strip()
        if not model:
            raise ValueError("ACTION_SUMMARY_MODEL must not be empty when summarization is enabled.")

        providers = {
            "openai": OpenAIProvider.from_env,
            "openrouter": OpenRouterProvider.from_env,
            "nvidia": NvidiaProvider.from_env,
        }
        provider = providers[configured_provider]()

        return cls(
            provider=provider,
            model=model,
            summary_source=configured_provider,
        )

    @staticmethod
    def _provider_has_credentials(provider_name: str) -> bool:
        if provider_name == "openai":
            return bool(os.environ.get("OPENAI_API_KEY", "").strip())
        if provider_name == "openrouter":
            return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
        if provider_name == "nvidia":
            return bool(os.environ.get("NVIDIA_API_KEY", "").strip())
        return False

    def summarize_action(
        self,
        *,
        query: str,
        function_call: types.FunctionCall,
        reasoning: str | None,
        current_url: str | None,
        previous_url: str | None = None,
        aria_diff: str | None = None,
    ) -> ActionStepSummary | None:
        prompt_payload = {
            "user_request": query,
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            "model_reasoning": reasoning,
            "previous_url": previous_url,
            "current_url": current_url,
            "aria_diff": aria_diff,
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
                    "Summarize the executed browser action as three short Korean fields.\n"
                    "Return JSON with keys what, why, outcome.\n"
                    "- what: a short Korean label (≤ 24 chars) describing the executed action.\n"
                    "- why: one concise Korean sentence explaining why this step was needed, grounded in the user request.\n"
                    "- outcome: one concise Korean sentence describing the concrete result observed. "
                    "Use `aria_diff` and URL change only as internal evidence. "
                    "If the outcome cannot be inferred, return '—'.\n"
                    "Never invent page details that are not present in the inputs.\n"
                    "Describe the result the way a non-technical end user would see it "
                    "(e.g. '검색 결과 목록이 표시됨', '로그인 폼이 나타남', '드라이버 다운로드 페이지로 이동'). "
                    "Never use the words 'ARIA', 'snapshot', 'frame', 'node', 'ref', 'diff', '트리', '구조', "
                    "and never quote raw diff syntax ('+', '-' line markers) or brace-wrapped tokens like '{Frame 1}'.\n\n"
                    f"{json.dumps(prompt_payload, ensure_ascii=False)}"
                ),
                max_tokens=220,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "action_step_summary",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "what": {"type": "string"},
                                "why": {"type": "string"},
                                "outcome": {"type": "string"},
                            },
                            "required": ["what", "why", "outcome"],
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

        what = parsed.get("what")
        why = parsed.get("why")
        outcome = parsed.get("outcome")
        if not isinstance(what, str) or not what.strip():
            return None
        if not isinstance(why, str) or not why.strip():
            return None
        if not isinstance(outcome, str) or not outcome.strip():
            return None

        return ActionStepSummary(
            what=_clean_summary_field(what, "동작 수행"),
            why=_clean_summary_field(why, "—"),
            outcome=_clean_summary_field(outcome, "—"),
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
