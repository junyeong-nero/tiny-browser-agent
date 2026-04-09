# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional, Any
from google.genai import types
import termcolor
from google.genai.types import (
    Part,
    GenerateContentConfig,
    Content,
    Candidate,
    FunctionResponse,
    FinishReason,
)
from rich.console import Console
from rich.table import Table

from computers import EnvState, Computer
from llm import LLMClient
from tool_calling import (
    BrowserToolExecutor,
    PREDEFINED_COMPUTER_USE_FUNCTIONS,
    ToolBatchResult,
    ToolResult,
    is_env_state_result,
    prune_old_screenshot_parts,
)

MAX_RECENT_TURN_WITH_SCREENSHOTS = 3


console = Console()

# Built-in Computer Use tools will return "EnvState".
# Custom provided functions will return "dict".
FunctionResponseT = ToolResult

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


def multiply_numbers(x: float, y: float) -> dict:
    """Multiplies two numbers."""
    return {"result": x * y}


class BrowserAgent:
    def __init__(
        self,
        browser_computer: Computer,
        query: str,
        model_name: str,
        verbose: bool = True,
        llm_client: Optional[LLMClient] = None,
        event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        self._browser_computer = browser_computer
        self._query = query
        self._model_name = model_name
        self._verbose = verbose
        self.final_reasoning = None
        self._llm_client = llm_client or LLMClient.from_env()
        self._event_sink = event_sink
        self._step_id = 0
        self._custom_functions = [multiply_numbers]
        self._action_review_history: list[ActionReviewContext] = []
        self._step_review_metadata: dict[int, dict[str, Any]] = {}
        self._tool_executor = BrowserToolExecutor(
            browser_computer=self._browser_computer,
            custom_functions=self._custom_functions,
        )
        self._contents: list[Content] = [
            Content(
                role="user",
                parts=[
                    Part(text=self._query),
                ],
            )
        ]

        # Exclude any predefined functions here.
        excluded_predefined_functions = []

        self._generate_content_config = GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            tools=self._tool_executor.build_tools(
                self._llm_client.build_function_declaration,
                excluded_predefined_functions=excluded_predefined_functions,
            ),
            # This agent handles function calls manually in `run_one_iteration`,
            # so SDK-side automatic function calling should stay disabled.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            thinking_config=types.ThinkingConfig(
                include_thoughts=True
            ),
        )

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if not self._event_sink:
            return
        self._event_sink(
            {
                "type": event_type,
                "timestamp": time.time(),
                **payload,
            }
        )

    def _emit_review_metadata(
        self,
        step_id: int,
        reasoning: Optional[str],
        final_result_summary: Optional[str] = None,
    ) -> None:
        step_review_metadata = self._step_review_metadata.get(step_id, {})
        if final_result_summary is not None:
            default_phase_id = "phase-complete"
            default_phase_label = "완료"
            default_user_visible_label = "결과 정리"
        else:
            default_phase_id = "all-steps"
            default_phase_label = "전체 과정 보기"
            default_user_visible_label = f"Step {step_id}"
        self._emit_event(
            "review_metadata_extracted",
            step_id=step_id,
            phase_id=step_review_metadata.get("phase_id", default_phase_id),
            phase_label=step_review_metadata.get("phase_label", default_phase_label),
            phase_summary=step_review_metadata.get("phase_summary", reasoning),
            user_visible_label=step_review_metadata.get(
                "user_visible_label",
                default_user_visible_label,
            ),
            verification_items=step_review_metadata.get(
                "verification_items",
                [],
            ),
            run_summary=reasoning,
            final_result_summary=final_result_summary,
            ambiguity_flag=step_review_metadata.get("ambiguity_flag"),
            ambiguity_type=step_review_metadata.get("ambiguity_type"),
            ambiguity_message=step_review_metadata.get(
                "ambiguity_message"
            ),
            review_evidence=step_review_metadata.get(
                "review_evidence",
                [],
            ),
            a11y_path=step_review_metadata.get("a11y_path"),
        )

    def append_user_message(self, text: str) -> None:
        self._contents.append(
            Content(
                role="user",
                parts=[Part(text=text)],
            )
        )

    def get_recent_messages(self, limit: int) -> list[dict[str, Optional[str]]]:
        messages: list[dict[str, Optional[str]]] = []
        for content in self._contents:
            if not content.parts:
                continue
            text_parts = [part.text for part in content.parts if part.text]
            if not text_parts:
                continue
            messages.append(
                {
                    "role": content.role,
                    "text": " ".join(text_parts),
                }
            )
        if limit <= 0:
            return []
        return messages[-limit:]

    def handle_action(self, action: types.FunctionCall) -> FunctionResponseT:
        """Handles the action and returns the environment state."""
        return self._tool_executor.execute(action)

    def get_model_response(self) -> types.GenerateContentResponse:
        return self._llm_client.generate_content(
            model=self._model_name,
            contents=self._contents,
            config=self._generate_content_config,
        )

    def get_text(self, candidate: Candidate) -> Optional[str]:
        """Extracts the text from the candidate."""
        if not candidate.content or not candidate.content.parts:
            return None
        text = []
        for part in candidate.content.parts:
            if part.text:
                text.append(part.text)
        return " ".join(text) or None

    def extract_function_calls(self, candidate: Candidate) -> list[types.FunctionCall]:
        """Extracts the function call from the candidate."""
        if not candidate.content or not candidate.content.parts:
            return []
        ret = []
        for part in candidate.content.parts:
            if part.function_call:
                ret.append(part.function_call)
        return ret

    def _request_model_response(
        self, step_id: int
    ) -> Optional[types.GenerateContentResponse]:
        if self._verbose:
            with console.status(
                "Generating response from Gemini Computer Use..."
            ):
                return self._request_model_response_once(step_id)
        return self._request_model_response_once(step_id)

    def _request_model_response_once(
        self, step_id: int
    ) -> Optional[types.GenerateContentResponse]:
        try:
            return self.get_model_response()
        except Exception as e:
            self._emit_event(
                "step_error",
                step_id=step_id,
                error_message=str(e),
            )
            print(e)
            return None

    def _extract_candidate_turn(
        self,
        step_id: int,
        response: types.GenerateContentResponse,
    ) -> tuple[Candidate, Optional[str], list[types.FunctionCall]]:
        if not response.candidates:
            self._emit_event(
                "step_error",
                step_id=step_id,
                error_message="Response has no candidates.",
            )
            print("Response has no candidates!")
            print(response)
            raise ValueError("Empty response")

        candidate = response.candidates[0]
        self._emit_event(
            "model_response",
            step_id=step_id,
            finish_reason=str(candidate.finish_reason) if candidate.finish_reason else None,
        )
        if candidate.content:
            self._contents.append(candidate.content)

        reasoning = self.get_text(candidate)
        self._emit_event("reasoning_extracted", step_id=step_id, reasoning=reasoning)
        function_calls = self.extract_function_calls(candidate)
        self._emit_event(
            "function_calls_extracted",
            step_id=step_id,
            function_calls=[
                {
                    "name": function_call.name,
                    "args": dict(function_call.args or {}),
                }
                for function_call in function_calls
            ],
        )
        return candidate, reasoning, function_calls

    def _should_retry_malformed_function_call(
        self,
        step_id: int,
        candidate: Candidate,
        reasoning: Optional[str],
        function_calls: list[types.FunctionCall],
    ) -> bool:
        if (
            not function_calls
            and not reasoning
            and candidate.finish_reason == FinishReason.MALFORMED_FUNCTION_CALL
        ):
            self._emit_event(
                "step_error",
                step_id=step_id,
                error_message="Malformed function call.",
            )
            return True
        return False

    def _complete_without_function_calls(
        self,
        step_id: int,
        reasoning: Optional[str],
    ) -> Literal["COMPLETE"]:
        print(f"Agent Loop Complete: {reasoning}")
        self.final_reasoning = reasoning
        self._emit_review_metadata(
            step_id=step_id,
            reasoning=reasoning,
            final_result_summary=reasoning,
        )
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status="complete",
            final_reasoning=reasoning,
        )
        return "COMPLETE"

    def _render_function_call_summary(
        self,
        reasoning: Optional[str],
        function_calls: list[types.FunctionCall],
    ) -> None:
        function_call_strs = []
        for function_call in function_calls:
            function_call_str = f"Name: {function_call.name}"
            if function_call.args:
                function_call_str += f"\nArgs:"
                for key, value in function_call.args.items():
                    function_call_str += f"\n  {key}: {value}"
            function_call_strs.append(function_call_str)

        table = Table(expand=True)
        table.add_column(
            "Gemini Computer Use Reasoning", header_style="magenta", ratio=1
        )
        table.add_column("Function Call(s)", header_style="cyan", ratio=1)
        table.add_row(reasoning, "\n".join(function_call_strs))
        if self._verbose:
            console.print(table)
            print()

    def _clean_reasoning_text(self, reasoning: Optional[str]) -> Optional[str]:
        if not reasoning:
            return None
        cleaned_reasoning = " ".join(reasoning.split())
        return cleaned_reasoning or None

    def _build_action_summary(self, function_call: types.FunctionCall) -> str:
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

    def _build_fallback_reason(self, function_call: types.FunctionCall) -> str:
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

    def _build_phase_metadata(
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
            "user_visible_label": self._build_action_summary(function_call)
            if function_call.name
            else f"Step {step_id}",
        }

    def _build_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        ambiguity_candidate: AmbiguityCandidate | None = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        cleaned_reasoning = self._clean_reasoning_text(reasoning)
        return {
            "action": {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
            },
            "action_summary": self._build_action_summary(function_call),
            "reason": cleaned_reasoning or self._build_fallback_reason(function_call),
            "reasoning_text": cleaned_reasoning,
            "summary_source": "app_derived",
            "model_step_id": step_id,
            "function_call_index_within_step": function_call_index,
            "ambiguity_flag": ambiguity_candidate is not None,
            "ambiguity_type": ambiguity_candidate.ambiguity_type if ambiguity_candidate else None,
            "ambiguity_message": ambiguity_candidate.message if ambiguity_candidate else None,
            "review_evidence": ambiguity_candidate.review_evidence if ambiguity_candidate else [],
            "a11y_path": artifacts.get("a11y_path") if artifacts else None,
        }

    def _resolve_metadata_file_path(
        self,
        artifacts: Optional[dict[str, Any]],
    ) -> Optional[Path]:
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

    def _enrich_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
        ambiguity_candidate: AmbiguityCandidate | None,
    ) -> None:
        metadata_file_path = self._resolve_metadata_file_path(artifacts)
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
            **self._build_persisted_action_metadata(
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

    def _build_review_metadata_for_action(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        current_context = ActionReviewContext(
            action_name=function_call.name or "action",
            action_args=dict(function_call.args or {}),
            current_url=artifacts.get("url") if artifacts else None,
        )
        previous_context = self._action_review_history[-1] if self._action_review_history else None
        ambiguity_candidate = detect_ambiguity_candidate(
            query=self._query,
            current_action=current_context,
            previous_action=previous_context,
        )
        self._action_review_history.append(current_context)

        review_metadata = {
            **self._build_phase_metadata(
                function_call=function_call,
                reasoning=reasoning,
                step_id=step_id,
            ),
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

    def _record_step_review_metadata(
        self,
        step_id: int,
        review_metadata: dict[str, Any],
    ) -> None:
        existing_metadata = self._step_review_metadata.get(step_id, {})
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

        self._step_review_metadata[step_id] = {
            "phase_id": existing_metadata.get("phase_id") or review_metadata.get("phase_id"),
            "phase_label": existing_metadata.get("phase_label") or review_metadata.get("phase_label"),
            "phase_summary": existing_metadata.get("phase_summary") or review_metadata.get("phase_summary"),
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

    def _execute_single_function_call(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        extra_fr_fields: dict[str, Any],
    ) -> FunctionResponse:
        if self._verbose:
            with console.status("Sending command to Computer..."):
                executed_call = self._tool_executor.execute_call(function_call)
        else:
            executed_call = self._tool_executor.execute_call(function_call)

        fc_result = executed_call.result
        action_payload = {
            "name": function_call.name,
            "args": dict(function_call.args or {}),
        }
        review_metadata = self._build_review_metadata_for_action(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=executed_call.function_call,
            reasoning=reasoning,
            artifacts=executed_call.artifacts,
        )
        self._record_step_review_metadata(step_id=step_id, review_metadata=review_metadata)
        self._enrich_persisted_action_metadata(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=executed_call.function_call,
            reasoning=reasoning,
            artifacts=executed_call.artifacts,
            ambiguity_candidate=(
                AmbiguityCandidate(
                    ambiguity_type=review_metadata["ambiguity_type"],
                    message=review_metadata["ambiguity_message"],
                    review_evidence=list(review_metadata.get("review_evidence") or []),
                )
                if review_metadata.get("ambiguity_flag")
                and review_metadata.get("ambiguity_type")
                and review_metadata.get("ambiguity_message")
                else None
            ),
        )
        if is_env_state_result(fc_result):
            self._emit_event(
                "action_executed",
                step_id=step_id,
                action=action_payload,
                env_state={
                    "url": fc_result.url,
                    "screenshot": fc_result.screenshot,
                },
                artifacts=executed_call.artifacts,
            )
        else:
            self._emit_event(
                "action_executed",
                step_id=step_id,
                action=action_payload,
                response=fc_result,
            )
        return self._tool_executor.serialize_function_response(
            executed_call,
            extra_response_fields=extra_fr_fields,
        )

    def _execute_function_calls(
        self,
        step_id: int,
        reasoning: Optional[str],
        function_calls: list[types.FunctionCall],
    ) -> ToolBatchResult:
        function_responses = []
        for function_call_index, function_call in enumerate(function_calls, start=1):
            extra_fr_fields = {}
            if function_call.args and (
                safety := function_call.args.get("safety_decision")
            ):
                decision = self._get_safety_confirmation(safety)
                if decision == "TERMINATE":
                    print("Terminating agent loop")
                    self._emit_event(
                        "step_complete",
                        step_id=step_id,
                        status="complete",
                        final_reasoning="Terminated after safety confirmation rejection.",
                    )
                    return ToolBatchResult(status="COMPLETE", function_responses=[])
                extra_fr_fields["safety_acknowledgement"] = "true"

            function_responses.append(
                self._execute_single_function_call(
                    step_id,
                    function_call_index,
                    function_call,
                    reasoning,
                    extra_fr_fields,
                )
            )

        return ToolBatchResult(
            status="CONTINUE",
            function_responses=function_responses,
        )

    def _append_function_responses(
        self,
        function_responses: list[FunctionResponse],
    ) -> None:
        self._contents.append(
            Content(
                role="user",
                parts=[Part(function_response=fr) for fr in function_responses],
            )
        )

    def _finalize_continuation_step(
        self,
        step_id: int,
        reasoning: Optional[str],
    ) -> Literal["CONTINUE"]:
        self._emit_review_metadata(step_id=step_id, reasoning=reasoning)
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status="complete",
        )
        return "CONTINUE"

    def run_one_iteration(self) -> Literal["COMPLETE", "CONTINUE"]:
        self._step_id += 1
        step_id = self._step_id
        self._emit_event("step_started", step_id=step_id)

        response = self._request_model_response(step_id)
        if response is None:
            return "COMPLETE"

        candidate, reasoning, function_calls = self._extract_candidate_turn(
            step_id,
            response,
        )

        if self._should_retry_malformed_function_call(
            step_id,
            candidate,
            reasoning,
            function_calls,
        ):
            return "CONTINUE"

        if not function_calls:
            return self._complete_without_function_calls(step_id, reasoning)

        self._render_function_call_summary(reasoning, function_calls)
        batch_result = self._execute_function_calls(
            step_id,
            reasoning,
            function_calls,
        )
        if batch_result.status == "COMPLETE":
            return "COMPLETE"

        self._append_function_responses(batch_result.function_responses)

        prune_old_screenshot_parts(
            self._contents,
            MAX_RECENT_TURN_WITH_SCREENSHOTS,
        )

        return self._finalize_continuation_step(step_id, reasoning)

    def _get_safety_confirmation(
        self, safety: dict[str, Any]
    ) -> Literal["CONTINUE", "TERMINATE"]:
        if safety["decision"] != "require_confirmation":
            raise ValueError(f"Unknown safety decision: safety['decision']")
        termcolor.cprint(
            "Safety service requires explicit confirmation!",
            color="yellow",
            attrs=["bold"],
        )
        print(safety["explanation"])
        decision = ""
        while decision.lower() not in ("y", "n", "ye", "yes", "no"):
            decision = input("Do you wish to proceed? [Yes]/[No]\n")
        if decision.lower() in ("n", "no"):
            return "TERMINATE"
        return "CONTINUE"

    def agent_loop(self):
        status = "CONTINUE"
        while status == "CONTINUE":
            status = self.run_one_iteration()

    def denormalize_x(self, x: int) -> int:
        return self._tool_executor.denormalize_x(x)

    def denormalize_y(self, y: int) -> int:
        return self._tool_executor.denormalize_y(y)
