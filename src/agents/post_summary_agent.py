import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import config as app_config

from google.genai import types

from llm.provider.openai import OpenAIProvider
from llm.provider.openrouter import OpenRouterProvider


# ---------------------------------------------------------------------------
# ActionStepSummary & summarizer
# ---------------------------------------------------------------------------


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

        model = os.environ.get("ACTION_SUMMARY_MODEL", app_config.summary_model()).strip()
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
        previous_url: str | None = None,
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
                    "- outcome: one concise Korean sentence describing the concrete result observed (e.g. URL change, form filled). "
                    "If the outcome cannot be inferred, return '—'.\n"
                    "Never invent page details that are not present in the inputs.\n\n"
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
                                "what":    {"type": "string"},
                                "why":     {"type": "string"},
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
            what=" ".join(what.split()),
            why=" ".join(why.split()),
            outcome=" ".join(outcome.split()),
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


# ---------------------------------------------------------------------------
# ActionReview
# ---------------------------------------------------------------------------


NAVIGATION_ACTION_NAMES = {
    "navigate",
    "search",
    "go_back",
    "go_forward",
    "open_web_browser",
}


@dataclass(frozen=True)
class ActionReviewContext:
    action_name: str
    action_args: dict[str, Any]
    current_url: str | None


@dataclass(frozen=True)
class AmbiguityCandidate:
    ambiguity_type: str
    message: str
    review_evidence: list[str]


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def detect_ambiguity_candidate(
    *,
    query: str,
    current_action: ActionReviewContext,
    previous_action: ActionReviewContext | None,
) -> AmbiguityCandidate | None:
    if current_action.action_name == "type_text_at":
        typed_text = current_action.action_args.get("text")
        if isinstance(typed_text, str):
            normalized_typed_text = _normalize_text(typed_text)
            if len(normalized_typed_text) >= 3 and normalized_typed_text not in _normalize_text(
                query
            ):
                return AmbiguityCandidate(
                    ambiguity_type="typed_text_not_in_query",
                    message="Entered text was not explicitly present in the original request.",
                    review_evidence=["typed_text_not_in_query"],
                )

    if (
        previous_action is not None
        and current_action.action_name in {"click_at", "type_text_at"}
        and current_action.action_name == previous_action.action_name
        and current_action.current_url == previous_action.current_url
        and current_action.action_args == previous_action.action_args
    ):
        evidence = (
            "repeated_click_pattern"
            if current_action.action_name == "click_at"
            else "repeated_type_pattern"
        )
        return AmbiguityCandidate(
            ambiguity_type=evidence,
            message="Repeated interaction was detected on the same page without new context.",
            review_evidence=[evidence],
        )

    if (
        previous_action is not None
        and previous_action.current_url
        and current_action.current_url
        and previous_action.current_url != current_action.current_url
        and current_action.action_name not in NAVIGATION_ACTION_NAMES
    ):
        return AmbiguityCandidate(
            ambiguity_type="url_changed_without_navigate",
            message="The page URL changed without an explicit navigation action.",
            review_evidence=["url_changed_without_navigate"],
        )

    return None


class ActionReviewService:
    def __init__(
        self,
        query: str,
        step_summarizer: ActionStepSummarizerProtocol | None = None,
    ):
        self._query = query
        self._action_review_history: list[ActionReviewContext] = []
        self._step_summarizer = step_summarizer
        self._step_summary_cache: dict[tuple[int, int], ActionStepSummary] = {}

    def build_final_result_summary(
        self,
        *,
        final_response: str | None,
        current_url: str | None,
    ) -> str | None:
        fallback_summary = self.clean_reasoning_text(final_response)
        if self._step_summarizer is None:
            return fallback_summary

        summarized = self._step_summarizer.summarize_final_result(
            query=self._query,
            final_response=final_response,
            current_url=current_url,
        )
        return summarized or fallback_summary

    def build_action_summary(self, function_call: types.FunctionCall) -> str:
        action_name = function_call.name or "action"
        action_args = dict(function_call.args or {})

        if action_name == "open_web_browser":
            return "Opened the web browser"
        if action_name == "click_at":
            return f"Clicked at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "hover_at":
            return f"Hovered at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "type_text_at":
            return f"Typed text at ({action_args.get('x')}, {action_args.get('y')})"
        if action_name == "scroll_document":
            return f"Scrolled the document {action_args.get('direction')}"
        if action_name == "scroll_at":
            return (
                f"Scrolled {action_args.get('direction')} at "
                f"({action_args.get('x')}, {action_args.get('y')})"
            )
        if action_name == "wait_5_seconds":
            return "Waited for 5 seconds"
        if action_name == "go_back":
            return "Went back to the previous page"
        if action_name == "go_forward":
            return "Went forward to the next page"
        if action_name == "search":
            return "Opened the search page"
        if action_name == "navigate":
            return f"Navigated to {action_args.get('url')}"
        if action_name == "key_combination":
            return f"Pressed key combination {action_args.get('keys')}"
        if action_name == "drag_and_drop":
            return (
                f"Dragged from ({action_args.get('x')}, {action_args.get('y')}) to "
                f"({action_args.get('destination_x')}, {action_args.get('destination_y')})"
            )
        return f"Executed {action_name}"

    def build_fallback_reason(self, function_call: types.FunctionCall) -> str:
        action_name = function_call.name or "action"
        action_args = dict(function_call.args or {})

        if action_name == "navigate":
            return f"Needed to open {action_args.get('url')}."
        if action_name == "click_at":
            return "Needed to click the selected page location."
        if action_name == "hover_at":
            return "Needed to inspect the selected page location."
        if action_name == "type_text_at":
            return "Needed to enter text into the page."
        if action_name in {"scroll_document", "scroll_at"}:
            return "Needed to move the page view to continue."
        if action_name == "wait_5_seconds":
            return "Needed to wait for the page state to settle."
        if action_name == "go_back":
            return "Needed to return to the previous page."
        if action_name == "go_forward":
            return "Needed to move forward in browser history."
        if action_name == "search":
            return "Needed to open the search page."
        if action_name == "key_combination":
            return "Needed to trigger a keyboard shortcut."
        if action_name == "drag_and_drop":
            return "Needed to move an on-page element."
        return f"Needed to execute {action_name}."

    def clean_reasoning_text(self, reasoning: Optional[str]) -> Optional[str]:
        if not reasoning:
            return None
        cleaned_reasoning = " ".join(reasoning.split())
        return cleaned_reasoning or None

    def build_phase_metadata(
        self,
        function_call: types.FunctionCall | None,
        reasoning: Optional[str],
        step_id: int,
        *,
        final_result_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        if final_result_summary is not None or function_call is None:
            return {
                "phase_id": "phase-complete",
                "phase_label": "완료",
                "phase_summary": reasoning,
                "user_visible_label": "결과 정리",
            }

        action_name = function_call.name or "action"
        if action_name in {"open_web_browser", "search", "navigate", "go_back", "go_forward"}:
            phase_id = "phase-navigation"
            phase_label = "페이지 이동"
        elif action_name in {"click_at", "hover_at"}:
            phase_id = "phase-interaction"
            phase_label = "페이지 상호작용"
        elif action_name in {"type_text_at", "key_combination", "drag_and_drop"}:
            phase_id = "phase-input"
            phase_label = "입력 및 조작"
        else:
            phase_id = "phase-observation"
            phase_label = "페이지 확인"

        return {
            "phase_id": phase_id,
            "phase_label": phase_label,
            "phase_summary": reasoning,
            "user_visible_label": self.build_action_summary(function_call)
            if function_call.name
            else f"Step {step_id}",
        }

    def _build_fallback_outcome(
        self,
        function_call: types.FunctionCall,
        current_url: str | None,
        previous_url: str | None,
    ) -> str:
        if current_url and previous_url and current_url != previous_url:
            try:
                from urllib.parse import urlparse
                host = urlparse(current_url).hostname or current_url
            except Exception:  # noqa: BLE001
                host = current_url
            return f"페이지 이동: {host}"
        action_name = function_call.name or ""
        if action_name in NAVIGATION_ACTION_NAMES:
            return "페이지 이동 요청 완료"
        return "—"

    def _get_action_step_summary(
        self,
        *,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        current_url: str | None,
        previous_url: str | None = None,
    ) -> ActionStepSummary:
        cache_key = (step_id, function_call_index)
        cached_summary = self._step_summary_cache.get(cache_key)
        if cached_summary is not None:
            return cached_summary

        fallback_summary = ActionStepSummary(
            what=self.build_action_summary(function_call),
            why=self.clean_reasoning_text(reasoning)
            or self.build_fallback_reason(function_call),
            outcome=self._build_fallback_outcome(function_call, current_url, previous_url),
            summary_source="app_derived",
        )

        if self._step_summarizer is None:
            self._step_summary_cache[cache_key] = fallback_summary
            return fallback_summary

        summarized = self._step_summarizer.summarize_action(
            query=self._query,
            function_call=function_call,
            reasoning=reasoning,
            current_url=current_url,
            previous_url=previous_url,
        )
        resolved_summary = summarized or fallback_summary
        self._step_summary_cache[cache_key] = resolved_summary
        return resolved_summary

    def build_review_metadata_for_action(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
        subgoal_id: int | None = None,
    ) -> dict[str, Any]:
        current_url = artifacts.get("url") if artifacts else None
        previous_context_for_url = (
            self._action_review_history[-1] if self._action_review_history else None
        )
        previous_url = previous_context_for_url.current_url if previous_context_for_url else None
        action_step_summary = self._get_action_step_summary(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            current_url=current_url,
            previous_url=previous_url,
        )
        current_context = ActionReviewContext(
            action_name=function_call.name or "action",
            action_args=dict(function_call.args or {}),
            current_url=current_url,
        )
        previous_context = self._action_review_history[-1] if self._action_review_history else None
        ambiguity_candidate = detect_ambiguity_candidate(
            query=self._query,
            current_action=current_context,
            previous_action=previous_context,
        )
        self._action_review_history.append(current_context)

        review_metadata = {
            **self.build_phase_metadata(
                function_call=function_call,
                reasoning=reasoning,
                step_id=step_id,
            ),
            "what": action_step_summary.what,
            "why": action_step_summary.why,
            "outcome": action_step_summary.outcome,
            "action_summary": action_step_summary.action_summary,
            "reason": action_step_summary.reason,
            "summary_source": action_step_summary.summary_source,
            "subgoal_id": subgoal_id,
            "user_visible_label": action_step_summary.action_summary,
            "ambiguity_flag": ambiguity_candidate is not None,
            "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
            "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
            "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
            "a11y_path": artifacts.get("a11y_path") if artifacts else None,
            "verification_items": [],
        }
        if ambiguity_candidate is None:
            return review_metadata

        review_metadata["verification_items"] = [
            {
                "id": f"ambiguity-step-{step_id}-{function_call_index}",
                "message": ambiguity_candidate.message,
                "detail": f"Review evidence: {', '.join(ambiguity_candidate.review_evidence)}",
                "source_step_id": step_id,
                "status": "needs_review",
                "a11y_path": artifacts.get("a11y_path") if artifacts else None,
                "ambiguity_flag": True,
                "ambiguity_type": ambiguity_candidate.ambiguity_type,
                "ambiguity_message": ambiguity_candidate.message,
                "review_evidence": ambiguity_candidate.review_evidence,
            }
        ]
        return review_metadata

    def build_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        ambiguity_candidate: AmbiguityCandidate | None = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        cleaned_reasoning = self.clean_reasoning_text(reasoning)
        action_step_summary = self._get_action_step_summary(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            current_url=artifacts.get("url") if artifacts else None,
        )
        return {
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            "what": action_step_summary.what,
            "why": action_step_summary.why,
            "outcome": action_step_summary.outcome,
            "action_summary": action_step_summary.action_summary,
            "reason": action_step_summary.reason,
            "reasoning_text": cleaned_reasoning,
            "summary_source": action_step_summary.summary_source,
            "model_step_id": step_id,
            "function_call_index_within_step": function_call_index,
            "ambiguity_flag": ambiguity_candidate is not None,
            "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
            "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
            "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
            "a11y_path": artifacts.get("a11y_path") if artifacts else None,
        }

    def merge_step_review_metadata(
        self,
        existing_metadata: dict[str, Any],
        review_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        verification_items = existing_metadata.get("verification_items", [])
        if review_metadata.get("verification_items"):
            verification_items = verification_items + review_metadata["verification_items"]

        existing_evidence = list(existing_metadata.get("review_evidence", []))
        merged_evidence = existing_evidence + [
            evidence
            for evidence in review_metadata.get("review_evidence", [])
            if evidence not in existing_evidence
        ]

        ambiguity_flag = bool(existing_metadata.get("ambiguity_flag")) or bool(
            review_metadata.get("ambiguity_flag")
        )
        ambiguity_type = existing_metadata.get("ambiguity_type")
        ambiguity_message = existing_metadata.get("ambiguity_message")
        if review_metadata.get("ambiguity_flag"):
            ambiguity_type = review_metadata.get("ambiguity_type") or ambiguity_type
            ambiguity_message = review_metadata.get("ambiguity_message") or ambiguity_message

        return {
            "phase_id": existing_metadata.get("phase_id") or review_metadata.get("phase_id"),
            "phase_label": existing_metadata.get("phase_label") or review_metadata.get("phase_label"),
            "phase_summary": existing_metadata.get("phase_summary") or review_metadata.get("phase_summary"),
            "what": existing_metadata.get("what") or review_metadata.get("what"),
            "why": existing_metadata.get("why") or review_metadata.get("why"),
            "outcome": existing_metadata.get("outcome") or review_metadata.get("outcome"),
            "action_summary": existing_metadata.get("action_summary")
            or review_metadata.get("action_summary"),
            "reason": existing_metadata.get("reason") or review_metadata.get("reason"),
            "summary_source": existing_metadata.get("summary_source")
            or review_metadata.get("summary_source"),
            "subgoal_id": existing_metadata.get("subgoal_id")
            if existing_metadata.get("subgoal_id") is not None
            else review_metadata.get("subgoal_id"),
            "user_visible_label": existing_metadata.get("user_visible_label")
            or review_metadata.get("user_visible_label"),
            "ambiguity_flag": ambiguity_flag,
            "ambiguity_type": ambiguity_type,
            "ambiguity_message": ambiguity_message,
            "review_evidence": merged_evidence,
            "a11y_path": review_metadata.get("a11y_path")
            or existing_metadata.get("a11y_path"),
            "verification_items": verification_items,
        }


# ---------------------------------------------------------------------------
# ActionMetadataWriter
# ---------------------------------------------------------------------------


class ActionMetadataWriter:
    def __init__(self, browser_computer: Any, review_service: ActionReviewService):
        self._browser_computer = browser_computer
        self._review_service = review_service

    def resolve_metadata_file_path(
        self,
        artifacts: dict[str, Any] | None,
    ) -> Path | None:
        if not artifacts:
            return None

        metadata_path_value = artifacts.get("metadata_path")
        if not isinstance(metadata_path_value, str) or not metadata_path_value:
            return None

        metadata_path = Path(metadata_path_value)
        if metadata_path.is_absolute():
            return metadata_path

        history_dir_getter = getattr(self._browser_computer, "history_dir", None)
        if not callable(history_dir_getter):
            return None

        history_dir = history_dir_getter()
        if history_dir is None:
            return None
        if not isinstance(history_dir, (str, Path)):
            return None

        return Path(history_dir) / metadata_path

    def enrich_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: str | None,
        artifacts: dict[str, Any] | None,
        ambiguity_candidate: AmbiguityCandidate | None,
    ) -> None:
        metadata_file_path = self.resolve_metadata_file_path(artifacts)
        if metadata_file_path is None or not metadata_file_path.exists():
            return

        try:
            existing_metadata = json.loads(metadata_file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(existing_metadata, dict):
            return

        enriched_metadata = {
            **existing_metadata,
            **self._review_service.build_persisted_action_metadata(
                step_id=step_id,
                function_call_index=function_call_index,
                function_call=function_call,
                reasoning=reasoning,
                ambiguity_candidate=ambiguity_candidate,
                artifacts=artifacts,
            ),
        }
        temp_file_path = metadata_file_path.with_name(f"{metadata_file_path.name}.tmp")

        try:
            temp_file_path.write_text(
                json.dumps(enriched_metadata, indent=2) + "\n",
                encoding="utf-8",
            )
            temp_file_path.replace(metadata_file_path)
        except OSError:
            temp_file_path.unlink(missing_ok=True)
