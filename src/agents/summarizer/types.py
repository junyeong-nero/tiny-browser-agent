from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types


@dataclass(frozen=True)
class ActionStepSummary:
    what: str
    why: str
    outcome: str
    summary_source: str

    # Backward-compat accessors for callers that still read the old field names.
    @property
    def action_summary(self) -> str:
        return self.what

    @property
    def reason(self) -> str:
        return self.why


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
        previous_url: str | None = None,
        aria_diff: str | None = None,
    ) -> ActionStepSummary | None: ...

    def summarize_final_result(
        self,
        *,
        query: str,
        final_response: str | None,
        current_url: str | None,
    ) -> str | None: ...

