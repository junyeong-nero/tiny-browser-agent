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
import time
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

from action_metadata import ActionMetadataWriter
from action_review import (
    ActionReviewContext,
    ActionReviewService,
    AmbiguityCandidate,
    detect_ambiguity_candidate,
)
from action_step_summarizer import ActionStepSummarizer
from browser_actions import build_browser_action_functions
from computers import EnvState, Computer
from llm import LLMClient
from tool_calling import (
    BrowserToolExecutor,
    ToolBatchResult,
    ToolResult,
    is_env_state_result,
    prune_old_screenshot_parts,
)

MAX_RECENT_TURN_WITH_SCREENSHOTS = 3
_UNSET_STEP_SUMMARIZER: object = object()

MODEL_REQUEST_MAX_ATTEMPTS = 4
MODEL_REQUEST_BASE_DELAY_SECONDS = 1.0
MODEL_REQUEST_MAX_DELAY_SECONDS = 16.0


console = Console()

# Built-in Computer Use tools will return "EnvState".
# Custom provided functions will return "dict".
FunctionResponseT = ToolResult


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
        step_summarizer: ActionStepSummarizer | None = _UNSET_STEP_SUMMARIZER,  # type: ignore[assignment]
    ):
        self._browser_computer = browser_computer
        self._query = query
        self._model_name = model_name
        self._verbose = verbose
        self.final_reasoning = None
        self._llm_client = llm_client or LLMClient.from_env()
        self._event_sink = event_sink
        self._step_id = 0
        self._custom_functions = [
            multiply_numbers,
            *build_browser_action_functions(browser_computer),
        ]
        self._step_review_metadata: dict[int, dict[str, Any]] = {}
        self._latest_url: str | None = None
        if step_summarizer is _UNSET_STEP_SUMMARIZER:
            step_summarizer = ActionStepSummarizer.from_env()
        self._tool_executor = BrowserToolExecutor(
            browser_computer=self._browser_computer,
            custom_functions=self._custom_functions,
        )
        self._review_service = ActionReviewService(
            query=self._query,
            step_summarizer=step_summarizer,
        )
        self._metadata_writer = ActionMetadataWriter(
            browser_computer=self._browser_computer,
            review_service=self._review_service,
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
            action_summary=step_review_metadata.get(
                "action_summary",
                step_review_metadata.get("user_visible_label", default_user_visible_label),
            ),
            reason=step_review_metadata.get("reason", reasoning),
            summary_source=step_review_metadata.get("summary_source", "app_derived"),
            user_visible_label=step_review_metadata.get(
                "user_visible_label",
                default_user_visible_label,
            ),
            verification_items=step_review_metadata.get(
                "verification_items",
                [],
            ),
            run_summary=final_result_summary or reasoning,
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
        return self._collect_text(candidate, include_thoughts=True)

    def get_visible_text(self, candidate: Candidate) -> Optional[str]:
        """Extracts only user-visible text from the candidate."""
        return self._collect_text(candidate, include_thoughts=False)

    def _collect_text(
        self,
        candidate: Candidate,
        *,
        include_thoughts: bool,
    ) -> Optional[str]:
        if not candidate.content or not candidate.content.parts:
            return None
        text = []
        for part in candidate.content.parts:
            if part.text and (include_thoughts or not getattr(part, "thought", False)):
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
        last_error: Optional[Exception] = None
        for attempt in range(1, MODEL_REQUEST_MAX_ATTEMPTS + 1):
            try:
                return self.get_model_response()
            except Exception as e:
                last_error = e
                if not self._should_retry_model_request(e) or attempt == MODEL_REQUEST_MAX_ATTEMPTS:
                    break
                delay = min(
                    MODEL_REQUEST_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
                    MODEL_REQUEST_MAX_DELAY_SECONDS,
                )
                self._emit_event(
                    "model_request_retry",
                    step_id=step_id,
                    attempt=attempt,
                    delay_seconds=delay,
                    error_message=str(e),
                )
                print(f"Gemini request failed (attempt {attempt}/{MODEL_REQUEST_MAX_ATTEMPTS}): {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
        self._emit_event(
            "step_error",
            step_id=step_id,
            error_message=str(last_error),
        )
        print(last_error)
        return None

    @staticmethod
    def _should_retry_model_request(error: Exception) -> bool:
        message = str(error).lower()
        status_code = getattr(error, "code", None) or getattr(error, "status_code", None)
        if isinstance(status_code, int) and status_code in {408, 429, 500, 502, 503, 504}:
            return True
        retryable_markers = (
            "timeout",
            "timed out",
            "temporarily unavailable",
            "temporarily_unavailable",
            "service unavailable",
            "unavailable",
            "internal error",
            "deadline exceeded",
            "rate limit",
            "resource_exhausted",
            "resource exhausted",
            "connection reset",
            "connection aborted",
            "connection error",
            "broken pipe",
            "retry",
        )
        return any(marker in message for marker in retryable_markers)

    def _extract_candidate_turn(
        self,
        step_id: int,
        response: types.GenerateContentResponse,
    ) -> tuple[Candidate, Optional[str], Optional[str], list[types.FunctionCall]]:
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
        visible_text = self.get_visible_text(candidate)
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
        return candidate, reasoning, visible_text, function_calls

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
        visible_text: Optional[str],
    ) -> Literal["COMPLETE"]:
        print(f"Agent Loop Complete: {reasoning}")
        final_reasoning = reasoning or visible_text
        final_result_summary = self._review_service.build_final_result_summary(
            final_response=visible_text or reasoning,
            current_url=self._latest_url,
        )
        self.final_reasoning = final_reasoning
        self._emit_review_metadata(
            step_id=step_id,
            reasoning=reasoning,
            final_result_summary=final_result_summary,
        )
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status="complete",
            final_reasoning=final_reasoning,
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
        return self._review_service.clean_reasoning_text(reasoning)

    def _build_action_summary(self, function_call: types.FunctionCall) -> str:
        return self._review_service.build_action_summary(function_call)

    def _build_fallback_reason(self, function_call: types.FunctionCall) -> str:
        return self._review_service.build_fallback_reason(function_call)

    def _build_phase_metadata(
        self,
        function_call: types.FunctionCall | None,
        reasoning: Optional[str],
        step_id: int,
        *,
        final_result_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._review_service.build_phase_metadata(
            function_call=function_call,
            reasoning=reasoning,
            step_id=step_id,
            final_result_summary=final_result_summary,
        )

    def _build_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        ambiguity_candidate: AmbiguityCandidate | None = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._review_service.build_persisted_action_metadata(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            ambiguity_candidate=ambiguity_candidate,
            artifacts=artifacts,
        )

    def _resolve_metadata_file_path(
        self,
        artifacts: Optional[dict[str, Any]],
    ) -> Optional[Path]:
        return self._metadata_writer.resolve_metadata_file_path(artifacts)

    def _enrich_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
        ambiguity_candidate: AmbiguityCandidate | None,
    ) -> None:
        self._metadata_writer.enrich_persisted_action_metadata(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            artifacts=artifacts,
            ambiguity_candidate=ambiguity_candidate,
        )

    def _build_review_metadata_for_action(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        artifacts: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._review_service.build_review_metadata_for_action(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=function_call,
            reasoning=reasoning,
            artifacts=artifacts,
        )

    def _record_step_review_metadata(
        self,
        step_id: int,
        review_metadata: dict[str, Any],
    ) -> None:
        existing_metadata = self._step_review_metadata.get(step_id, {})
        self._step_review_metadata[step_id] = self._review_service.merge_step_review_metadata(
            existing_metadata=existing_metadata,
            review_metadata=review_metadata,
        )

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
            self._latest_url = fc_result.url
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

        candidate, reasoning, visible_text, function_calls = self._extract_candidate_turn(
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
            return self._complete_without_function_calls(step_id, reasoning, visible_text)

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
