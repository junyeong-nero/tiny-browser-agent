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
from typing import Callable, Literal, Optional, Any
from google.genai import types
from google.genai.types import (
    Part,
    GenerateContentConfig,
    Content,
    Candidate,
    FunctionResponse,
)
from rich.console import Console
from rich.table import Table

import config as app_config
from agents.summarizer import (
    ActionMetadataWriter,
    ActionReviewService,
    ActionStepSummarizer,
)
from core.navigation_scope import NavigationScope
from core.types import AgentRunResult, AgentRunStatus, GroundingMode, Subgoal
from . import model_trace, model_turn, subgoal_runner, subgoals as subgoal_helpers
from . import tool_orchestration
from .context_compaction import build_effective_contents
from .prompts import _ACTOR_SYSTEM_PROMPT, build_initial_prompt
from .provider_modes import (
    COMPUTER_USE_PROVIDER_NAMES,
    validate_grounding_provider,
)
from .review_events import build_review_metadata_event_payload
from .safety import (
    SafetyConfirmationCallback,
    SafetyDecision,
    prompt_for_safety_confirmation,
)
from browser import (
    ArtifactLogger,
    BrowserActionName,
    DEFAULT_BROWSER_ACTIONS,
    build_browser_action_functions,
    EnvState,
    PlaywrightBrowser,
)
from llm import LLMClient
from tool_executor import BrowserToolExecutor, prune_old_aria_parts, prune_old_screenshot_parts
from tools.helpers import resolve_ref_node
from tools.types import (
    CustomFunction,
    ExecutedCall,
    ToolBatchResult,
    extract_tool_argument_error,
    is_env_state_result,
)

MAX_RECENT_TURN_WITH_SCREENSHOTS = 3
MAX_RECENT_TURNS_WITH_ARIA = 1
MAX_RECENT_CONTEXT_TURNS = 8
COMPACT_CONTEXT_AFTER_TURNS = 16
_UNSET_STEP_SUMMARIZER: object = object()

MODEL_REQUEST_MAX_ATTEMPTS = 4
MODEL_REQUEST_BASE_DELAY_SECONDS = 1.0
MODEL_REQUEST_MAX_DELAY_SECONDS = 16.0
EMPTY_MODEL_TURN_MAX_RETRIES = 2


class AgentInterrupted(Exception):
    """Raised when the current browser-agent task is cooperatively interrupted."""


console = Console()


class BrowserAgent:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        query: str,
        model_name: str,
        verbose: bool = True,
        llm_client: Optional[LLMClient] = None,
        event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
        step_summarizer: ActionStepSummarizer | None = _UNSET_STEP_SUMMARIZER,  # type: ignore[assignment]
        artifact_logger: Optional[ArtifactLogger] = None,
        grounding: GroundingMode = "vision",
        subgoals: list[Subgoal] | None = None,
        replan_callback: Optional[Callable[..., list[Subgoal]]] = None,
        max_steps_per_subgoal: int = 15,
        conversation_context: str | None = None,
        custom_functions: list[CustomFunction] | None = None,
        extra_browser_tools: list[BrowserActionName] | None = None,
        interrupt_checker: Callable[[], bool] | None = None,
        safety_confirmation_callback: SafetyConfirmationCallback | None = None,
        max_total_steps: int = 100,
        max_subgoals: int = 10,
    ):
        self._browser_computer = browser_computer
        self._query = query
        self._model_name = model_name
        self._verbose = verbose
        self.final_reasoning = None
        if llm_client is not None:
            self._llm_client = llm_client
        else:
            # BrowserAgent owns model-turn retry/backoff and emits UI-visible retry
            # events. Keep the lower-level provider wrapper single-shot here to
            # avoid multiplying retries for every actor step.
            self._llm_client = LLMClient.from_provider_name(
                app_config.actor_provider(),
                max_retries=1,
            )

        provider_name = self._llm_client.provider_name
        self._validate_grounding_provider(grounding, provider_name)
        self._event_sink = event_sink
        self._artifact_logger = artifact_logger if artifact_logger is not None else ArtifactLogger()
        self._step_id = 0
        self._grounding = grounding
        self._subgoals = subgoals
        self._replan_callback = replan_callback
        self._max_steps_per_subgoal = max_steps_per_subgoal
        self._interrupt_checker = interrupt_checker
        self._safety_confirmation_callback = safety_confirmation_callback
        self._max_total_steps = max_total_steps
        self._max_subgoals = max_subgoals
        self._total_steps_used = 0
        browser_actions = build_browser_action_functions(
            browser_computer,
            include=(*DEFAULT_BROWSER_ACTIONS, *(extra_browser_tools or [])),
        )
        self._custom_functions = [
            *browser_actions,
            *(custom_functions or []),
        ]
        self._step_review_metadata: dict[int, dict[str, Any]] = {}
        self._last_model_request_context: dict[str, Any] | None = None
        self._last_final_response: str | None = None
        self._latest_url: str | None = None
        self._current_subgoal_id: int | None = None
        self._empty_model_turn_retries = 0
        self._navigation_scope = NavigationScope.from_query(self._query)
        if step_summarizer is _UNSET_STEP_SUMMARIZER:
            step_summarizer = ActionStepSummarizer.from_env()
        self._tool_executor = BrowserToolExecutor(
            browser_computer=self._browser_computer,
            custom_functions=self._custom_functions,
            grounding=grounding,
            navigation_scope=self._navigation_scope,
            use_computer_use_tools=provider_name in COMPUTER_USE_PROVIDER_NAMES,
        )
        self._review_service = ActionReviewService(
            query=self._query,
            step_summarizer=step_summarizer,
        )
        self._metadata_writer = ActionMetadataWriter(
            browser_computer=self._browser_computer,
            review_service=self._review_service,
        )
        initial_prompt = self._build_initial_prompt(
            query=self._query,
            conversation_context=conversation_context,
            navigation_scope=self._navigation_scope,
        )
        self._contents: list[Content] = [
            Content(
                role="user",
                parts=[
                    Part(text=initial_prompt),
                ],
            )
        ]

        # `navigate` covers direct search-engine navigation while keeping the
        # exposed Computer Use tool set smaller.
        excluded_predefined_functions = ["search"]

        self._generate_content_config = GenerateContentConfig(
            system_instruction=Content(
                role="system",
                parts=[Part(text=_ACTOR_SYSTEM_PROMPT)],
            ),
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

    def _raise_if_interrupted(self) -> None:
        if self._interrupt_checker is not None and self._interrupt_checker():
            self._emit_event(
                "step_error",
                step_id=self._step_id,
                error_message="Task interrupted by user.",
            )
            raise AgentInterrupted("Task interrupted by user.")

    @staticmethod
    def _build_initial_prompt(
        *,
        query: str,
        conversation_context: str | None,
        navigation_scope: NavigationScope | None = None,
    ) -> str:
        return build_initial_prompt(
            query=query,
            conversation_context=conversation_context,
            navigation_scope=navigation_scope,
        )

    @property
    def latest_url(self) -> str | None:
        return self._latest_url

    @staticmethod
    def _validate_grounding_provider(
        grounding: GroundingMode,
        provider_name: str,
    ) -> None:
        validate_grounding_provider(grounding, provider_name)

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
        self._emit_event(
            "review_metadata_extracted",
            **build_review_metadata_event_payload(
                step_id=step_id,
                step_review_metadata=self._step_review_metadata.get(step_id, {}),
                reasoning=reasoning,
                final_result_summary=final_result_summary,
                current_subgoal_id=self._current_subgoal_id,
            ),
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

    def get_model_response(self) -> types.GenerateContentResponse:
        effective_contents = build_effective_contents(
            self._contents,
            query=self._query,
            current_subgoal_id=self._current_subgoal_id,
            recent_turn_limit=MAX_RECENT_CONTEXT_TURNS,
            compact_after=COMPACT_CONTEXT_AFTER_TURNS,
        )
        self._last_model_request_context = {
            "model": self._model_name,
            "system_instruction": model_trace.serialize_content(
                self._generate_content_config.system_instruction
            ),
            "contents": [
                model_trace.serialize_content(content)
                for content in effective_contents
            ],
        }
        return self._llm_client.generate_content(
            model=self._model_name,
            contents=effective_contents,
            config=self._generate_content_config,
        )

    def get_text(self, candidate: Candidate) -> Optional[str]:
        """Extracts the text from the candidate."""
        return model_turn.collect_text(candidate, include_thoughts=True)

    def get_visible_text(self, candidate: Candidate) -> Optional[str]:
        """Extracts only user-visible text from the candidate."""
        return model_turn.collect_text(candidate, include_thoughts=False)

    def _collect_text(
        self,
        candidate: Candidate,
        *,
        include_thoughts: bool,
    ) -> Optional[str]:
        return model_turn.collect_text(candidate, include_thoughts=include_thoughts)

    @staticmethod
    def _strip_thought_parts(content: Content) -> Content:
        """Return a copy of `content` with thought parts removed.

        Persisting thought parts in `_contents` is not portable across providers
        and can trigger validation errors when replayed to models that do not
        support the `thought` flag.
        """
        return model_turn.strip_thought_parts(content)

    def extract_function_calls(self, candidate: Candidate) -> list[types.FunctionCall]:
        """Extracts the function call from the candidate."""
        return model_turn.extract_function_calls(candidate)

    def _request_model_response(
        self, step_id: int
    ) -> types.GenerateContentResponse:
        if self._verbose:
            with console.status(
                "Generating response from actor model..."
            ):
                return self._request_model_response_once(step_id)
        return self._request_model_response_once(step_id)

    def _request_model_response_once(
        self, step_id: int
    ) -> types.GenerateContentResponse:
        last_error: Optional[Exception] = None
        for attempt in range(1, MODEL_REQUEST_MAX_ATTEMPTS + 1):
            try:
                response = self.get_model_response()
                self._emit_event(
                    "llm_inference",
                    step_id=step_id,
                    raw_context=self._last_model_request_context,
                    raw_response=model_trace.serialize_model_response(response),
                )
                return response
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
                print(f"Model request failed (attempt {attempt}/{MODEL_REQUEST_MAX_ATTEMPTS}): {e}. Retrying in {delay:.1f}s...")
                self._sleep_with_interrupt(delay)
        self._emit_event(
            "step_error",
            step_id=step_id,
            error_message=str(last_error),
        )
        print(last_error)
        raise RuntimeError(f"Model request failed after retries: {last_error}") from last_error

    def _sleep_with_interrupt(self, delay_seconds: float) -> None:
        deadline = time.monotonic() + delay_seconds
        while True:
            self._raise_if_interrupted()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.2, remaining))

    @staticmethod
    def _should_retry_model_request(error: Exception) -> bool:
        return model_turn.should_retry_model_request(error)

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
            self._contents.append(self._strip_thought_parts(candidate.content))

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
        if model_turn.is_malformed_function_call_turn(
            candidate,
            reasoning=reasoning,
            function_calls=function_calls,
        ):
            if self._contents and self._contents[-1].role == "model":
                self._contents.pop()
            self._emit_event(
                "step_error",
                step_id=step_id,
                error_message="Malformed function call.",
            )
            self.append_user_message(
                "Your previous response contained a malformed function call. "
                "Retry the previous step with valid tool-call JSON, or finish "
                "with a concise visible final answer."
            )
            self._emit_event(
                "step_complete",
                step_id=step_id,
                status="retry",
                error_message="Malformed function call.",
            )
            return True
        return False

    def _should_retry_unsupported_function_call(
        self,
        step_id: int,
        candidate: Candidate,
        function_calls: list[types.FunctionCall],
    ) -> bool:
        unsupported_names = [
            function_call.name or "<missing name>"
            for function_call in function_calls
            if not self._tool_executor.supports_function(function_call.name)
        ]
        if not unsupported_names:
            return False

        # The model turn is not executable and may be rejected by chat-completion
        # providers if replayed without a matching tool response. Remove it and
        # ask the model for a fresh response using only supported tools.
        if self._contents and self._contents[-1].role == "model":
            self._contents.pop()

        allowed_names = sorted(
            {
                declaration.name
                for tool in (self._generate_content_config.tools or [])
                for declaration in (tool.function_declarations or [])
                if declaration.name
            }
        )
        allowed_summary = ", ".join(allowed_names) if allowed_names else "the declared browser tools"
        unsupported_summary = ", ".join(unsupported_names)
        error_message = (
            f"Unsupported function call(s): {unsupported_summary}. "
            "Retrying model turn with a corrective instruction."
        )
        self._emit_event(
            "step_error",
            step_id=step_id,
            error_message=error_message,
        )
        self.append_user_message(
            "Your previous response used an unsupported function call "
            f"({unsupported_summary}). Retry the previous step using only supported "
            f"tools: {allowed_summary}. If you intended to finish a planner subgoal, "
            "do not call SUBGOAL_DONE or SUBGOAL_FAILED as tools; write a final text "
            "message beginning with 'SUBGOAL_DONE:' or 'SUBGOAL_FAILED:' instead."
        )
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status="retry",
            error_message=error_message,
        )
        return True

    def _should_retry_empty_model_turn(
        self,
        step_id: int,
        reasoning: Optional[str],
        visible_text: Optional[str],
        function_calls: list[types.FunctionCall],
    ) -> bool:
        if visible_text or function_calls:
            self._empty_model_turn_retries = 0
            return False

        # Planner subgoal execution already has a marker-specific recovery path
        # for missing final text. Keep that behavior local to subgoals so a
        # blank turn can be classified as a failed subgoal/replanned instead of
        # aborting the whole planner run.
        if self._current_subgoal_id is not None:
            return False

        self._empty_model_turn_retries += 1
        error_message = (
            "Model returned no visible text and no tool calls. "
            f"Retrying empty turn ({self._empty_model_turn_retries}/"
            f"{EMPTY_MODEL_TURN_MAX_RETRIES})."
        )
        self._emit_event(
            "step_error",
            step_id=step_id,
            error_message=error_message,
        )

        # Do not replay an empty assistant turn to chat-completion providers;
        # some providers reject assistant messages with no content/tool calls.
        if self._contents and self._contents[-1].role == "model":
            latest_parts = self._contents[-1].parts or []
            if not any(part.text or part.function_call for part in latest_parts):
                self._contents.pop()

        if self._empty_model_turn_retries > EMPTY_MODEL_TURN_MAX_RETRIES:
            raise RuntimeError(
                "Model returned no text or tool calls after "
                f"{EMPTY_MODEL_TURN_MAX_RETRIES} retry attempts."
            )

        self.append_user_message(
            "Your previous response was empty: it contained neither a browser "
            "tool call nor a visible final answer. Continue the task by calling "
            "an appropriate browser tool, or finish with a concise visible final answer."
        )
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status="retry",
            error_message=error_message,
        )
        return True

    def _complete_without_function_calls(
        self,
        step_id: int,
        reasoning: Optional[str],
        visible_text: Optional[str],
    ) -> Literal["COMPLETE"]:
        raw_final_response = visible_text or reasoning
        self._last_final_response = raw_final_response
        final_result_summary = self._review_service.build_final_result_summary(
            final_response=raw_final_response,
            current_url=self._latest_url,
        )
        final_reasoning = final_result_summary or raw_final_response
        print(f"Agent Loop Complete: {final_reasoning or '<empty model response>'}")
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
            "Actor Reasoning", header_style="magenta", ratio=1
        )
        table.add_column("Function Call(s)", header_style="cyan", ratio=1)
        table.add_row(reasoning or "", "\n".join(function_call_strs))
        if self._verbose:
            console.print(table)
            print()

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
            subgoal_id=self._current_subgoal_id,
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

    def _build_tool_execution_error_call(
        self,
        function_call: types.FunctionCall,
        exc: Exception,
    ) -> ExecutedCall:
        return tool_orchestration.build_tool_execution_error_call(function_call, exc)

    def _resolve_ref_name(self, args: Any) -> Optional[str]:
        if not args or not hasattr(args, "get") or args.get("ref") is None:
            return None
        try:
            node = resolve_ref_node(self._browser_computer, dict(args))
        except (TypeError, ValueError):
            return None
        if node is None:
            return None
        name = (node.name or "").strip()
        if name:
            return name
        role = (getattr(node, "role", "") or "").strip()
        if role:
            return f"<{role}>"
        return None

    def _execute_single_function_call(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: Optional[str],
        extra_fr_fields: dict[str, Any],
    ) -> tuple[FunctionResponse, bool]:
        ref_name = self._resolve_ref_name(function_call.args)
        argument_error = extract_tool_argument_error(function_call.args)
        if argument_error is not None:
            error_message = str(argument_error.get("error") or "Malformed tool arguments.")
            self._emit_event(
                "step_error",
                step_id=step_id,
                error_message=error_message,
            )
            executed_call = ExecutedCall(
                function_call=function_call,
                result=argument_error,
                artifacts=None,
            )
        else:
            try:
                if self._verbose:
                    with console.status("Sending command to Computer..."):
                        executed_call = self._tool_executor.execute_call(function_call)
                else:
                    executed_call = self._tool_executor.execute_call(function_call)
            except AgentInterrupted:
                raise
            except Exception as exc:  # noqa: BLE001
                error_message = tool_orchestration.build_tool_execution_error_message(function_call, exc)
                self._emit_event(
                    "step_error",
                    step_id=step_id,
                    error_message=error_message,
                )
                executed_call = self._build_tool_execution_error_call(function_call, exc)

        fc_result = executed_call.result
        action_payload = tool_orchestration.action_payload_with_ref_name(function_call, ref_name)
        action_args = action_payload["args"]
        review_metadata = self._review_service.build_review_metadata_for_action(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=executed_call.function_call,
            reasoning=reasoning,
            artifacts=executed_call.artifacts,
            subgoal_id=self._current_subgoal_id,
        )
        self._record_step_review_metadata(step_id=step_id, review_metadata=review_metadata)
        self._metadata_writer.enrich_persisted_action_metadata(
            step_id=step_id,
            function_call_index=function_call_index,
            function_call=executed_call.function_call,
            reasoning=reasoning,
            artifacts=executed_call.artifacts,
            ambiguity_candidate=tool_orchestration.ambiguity_candidate_from_review_metadata(
                review_metadata
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
            result_summary = fc_result.url
        else:
            self._emit_event(
                "action_executed",
                step_id=step_id,
                action=action_payload,
                response=fc_result,
            )
            result_summary = str(fc_result)[:200] if fc_result is not None else None
        self._artifact_logger.record_action(
            tool=function_call.name,
            args=action_args,
            result_summary=result_summary,
        )
        function_response = self._tool_executor.serialize_function_response(
            executed_call,
            extra_response_fields=extra_fr_fields,
        )
        return function_response, is_env_state_result(fc_result)

    def _execute_function_calls(
        self,
        step_id: int,
        reasoning: Optional[str],
        function_calls: list[types.FunctionCall],
    ) -> ToolBatchResult:
        function_responses = []
        browser_state_observed = False
        for function_call_index, function_call in enumerate(function_calls, start=1):
            self._raise_if_interrupted()
            if browser_state_observed:
                function_responses.append(
                    tool_orchestration.build_reobserve_required_response(function_call)
                )
                continue

            extra_fr_fields = {}
            if function_call.args and (
                safety := function_call.args.get("safety_decision")
            ):
                decision = self._get_safety_confirmation(safety)
                if decision == "TERMINATE":
                    print("Terminating agent loop")
                    self.final_reasoning = "Terminated after safety confirmation rejection."
                    self._emit_event(
                        "step_complete",
                        step_id=step_id,
                        status="complete",
                        final_reasoning=self.final_reasoning,
                    )
                    return ToolBatchResult(status="COMPLETE", function_responses=[])
                extra_fr_fields["safety_acknowledgement"] = "true"

            function_response, produced_browser_state = self._execute_single_function_call(
                step_id,
                function_call_index,
                function_call,
                reasoning,
                extra_fr_fields,
            )
            function_responses.append(function_response)
            browser_state_observed = browser_state_observed or produced_browser_state

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
        self._raise_if_interrupted()
        self._step_id += 1
        step_id = self._step_id
        self._emit_event("step_started", step_id=step_id)

        response = self._request_model_response(step_id)
        self._raise_if_interrupted()

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

        if self._should_retry_unsupported_function_call(
            step_id,
            candidate,
            function_calls,
        ):
            return "CONTINUE"

        if self._should_retry_empty_model_turn(
            step_id,
            reasoning,
            visible_text,
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
        prune_old_aria_parts(
            self._contents,
            MAX_RECENT_TURNS_WITH_ARIA,
        )

        return self._finalize_continuation_step(step_id, reasoning)

    def _get_safety_confirmation(
        self, safety: dict[str, Any]
    ) -> SafetyDecision:
        if safety["decision"] != "require_confirmation":
            raise ValueError(f"Unknown safety decision: {safety['decision']}")
        self._emit_event(
            "safety_confirmation_required",
            step_id=self._step_id,
            explanation=safety.get("explanation"),
        )
        if self._safety_confirmation_callback is not None:
            return self._safety_confirmation_callback(safety)
        return prompt_for_safety_confirmation(safety)

    def _raise_if_total_step_budget_exceeded(self) -> None:
        if self._total_steps_used < self._max_total_steps:
            return
        message = f"Exceeded max total steps ({self._max_total_steps})."
        self._emit_event(
            "step_error",
            step_id=self._step_id,
            error_message=message,
        )
        raise RuntimeError(message)

    def _raise_if_subgoal_budget_exceeded(self, subgoal_count: int) -> None:
        if subgoal_count <= self._max_subgoals:
            return
        message = f"Exceeded max subgoals ({self._max_subgoals})."
        self._emit_event(
            "step_error",
            step_id=self._step_id,
            error_message=message,
        )
        raise RuntimeError(message)

    def _run_subgoal_loop(
        self,
        subgoal: Subgoal,
        prior_outcomes: list[tuple[Subgoal, Literal["done", "failed"], str]] | None = None,
    ) -> tuple[Literal["done", "failed"], str]:
        return subgoal_runner.run_subgoal_loop(self, subgoal, prior_outcomes or [])

    def _finalize_subgoal_plan(
        self,
        outcomes: list[tuple[Subgoal, Literal["done", "failed"], str]],
        *,
        status: AgentRunStatus | None = None,
        reason: str | None = None,
    ) -> AgentRunResult:
        if not outcomes:
            return AgentRunResult(status="blocked", reason=reason or "Planner produced no subgoal outcomes.")

        self._step_id += 1
        step_id = self._step_id
        raw_summary = subgoal_helpers.build_subgoal_plan_summary(outcomes)
        succeeded = sum(1 for _, result, _ in outcomes if result == "done")
        failed = sum(1 for _, result, _ in outcomes if result == "failed")
        final_status: AgentRunStatus = status or ("complete" if failed == 0 else "partial_failure")
        final_result_summary = self._review_service.build_final_result_summary(
            final_response=raw_summary,
            current_url=self._latest_url,
        )
        self.final_reasoning = final_result_summary or raw_summary
        print(f"Agent Loop Complete: {self.final_reasoning}")
        self._emit_review_metadata(
            step_id=step_id,
            reasoning=raw_summary,
            final_result_summary=self.final_reasoning,
        )
        self._emit_event(
            "step_complete",
            step_id=step_id,
            status=final_status,
            final_reasoning=self.final_reasoning,
            succeeded_subgoals=succeeded,
            failed_subgoals=failed,
            reason=reason,
        )
        return AgentRunResult(
            status=final_status,
            reason=reason,
            summary=self.final_reasoning,
            succeeded_subgoals=succeeded,
            failed_subgoals=failed,
        )

    def agent_loop(self) -> AgentRunResult:
        self._total_steps_used = 0
        if self._subgoals is None:
            status = "CONTINUE"
            while status == "CONTINUE":
                self._raise_if_interrupted()
                self._raise_if_total_step_budget_exceeded()
                status = self.run_one_iteration()
                self._total_steps_used += 1
            return AgentRunResult(status="complete", summary=self.final_reasoning)

        return subgoal_runner.run_subgoal_plan(self)
