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
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch
from google.genai import types
import config as app_config
from agents.actor_agent import BrowserAgent
from agents.post_summary_agent import ActionReviewService
from agents.types import Subgoal
from browser import EnvState
from llm.client import LLMClient
from tools.types import TOOL_ARGUMENT_ERROR_KEY


def multiply_numbers(x: float, y: float) -> dict:
    """Multiplies two numbers."""
    return {"result": x * y}


class TestBrowserAgent(unittest.TestCase):
    def setUp(self):
        self.mock_browser_computer = MagicMock()
        self.mock_browser_computer.screen_size.return_value = (1000, 1000)
        self.mock_browser_computer.latest_artifact_metadata.return_value = {
            "screenshot_path": "step-0001.png",
            "html_path": "step-0001.html",
            "metadata_path": "step-0001.json",
        }
        self.mock_browser_computer.history_dir.return_value = None
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.mock_llm_client.provider_name = "gemini_api"
        self.mock_llm_client.build_function_declaration.side_effect = (
            lambda callable_: types.FunctionDeclaration(
                name=callable_.__name__,
                description=callable_.__doc__,
                parameters_json_schema={"type": "object", "properties": {}},
            )
        )
        self.agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
        )

    def make_response(self, parts, finish_reason=None):
        response = MagicMock()
        candidate = MagicMock()
        candidate.content = types.Content(role="model", parts=parts)
        candidate.finish_reason = finish_reason
        response.candidates = [candidate]
        return response

    def make_screenshot_turn(self, name: str, screenshot: bytes) -> types.Content:
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name,
                        response={"url": f"https://example.com/{name}"},
                        parts=[
                            types.FunctionResponsePart(
                                inline_data=types.FunctionResponseBlob(
                                    mime_type="image/png",
                                    data=screenshot,
                                )
                            )
                        ],
                    )
                )
            ],
        )

    def get_tools(self) -> list[types.Tool]:
        tools = self.agent._generate_content_config.tools
        if tools is None:
            self.fail("Expected generate content tools")
        return cast(list[types.Tool], list(tools))

    def get_function_response(self, content: types.Content) -> types.FunctionResponse:
        if content.parts is None:
            self.fail("Expected content parts")
        function_response = content.parts[0].function_response
        if function_response is None:
            self.fail("Expected function response")
        return function_response

    def write_metadata_file(
        self,
        directory: Path,
        file_name: str,
        *,
        step: int,
        url: str,
    ) -> Path:
        metadata_path = directory / file_name
        metadata_path.write_text(
            json.dumps(
                {
                    "step": step,
                    "timestamp": 123.45,
                    "url": url,
                    "html_path": file_name.replace(".json", ".html"),
                    "screenshot_path": file_name.replace(".json", ".png"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return metadata_path

    def test_multiply_numbers(self):
        self.assertEqual(multiply_numbers(2, 3), {"result": 6})

    def test_automatic_function_calling_is_disabled(self):
        automatic_function_calling = self.agent._generate_content_config.automatic_function_calling
        if automatic_function_calling is None:
            self.fail("Expected automatic function calling config")
        self.assertTrue(automatic_function_calling.disable)

    def test_actor_uses_browser_system_instruction(self):
        system_instruction = self.agent._generate_content_config.system_instruction
        self.assertIsInstance(system_instruction, types.Content)
        assert isinstance(system_instruction, types.Content)
        self.assertEqual(system_instruction.role, "system")
        self.assertIsNotNone(system_instruction.parts)
        text = "\n".join(part.text or "" for part in system_instruction.parts or [])
        self.assertIn("browser automation agent", text)
        self.assertIn("Ground every browser action", text)
        self.assertIn("go_back does not change", text)
        self.assertIn("list_tabs", text)
        self.assertIn("switch_to_tab or close_current_tab", text)

    def test_vision_grounding_rejects_non_computer_use_provider(self):
        llm_client = MagicMock(spec=LLMClient)
        llm_client.provider_name = "openrouter"

        with self.assertRaisesRegex(ValueError, "requires a computer-use model provider"):
            BrowserAgent(
                browser_computer=self.mock_browser_computer,
                query="test query",
                model_name="test_model",
                llm_client=llm_client,
                grounding="vision",
                step_summarizer=None,
            )

    @patch("agents.actor_agent.LLMClient.from_provider_name")
    def test_default_config_provider_is_compatible_with_text_grounding(
        self,
        mock_from_provider_name,
    ):
        expected_provider = app_config.actor_provider()
        llm_client = MagicMock(spec=LLMClient)
        llm_client.provider_name = expected_provider
        llm_client.build_function_declaration.side_effect = (
            lambda callable_: types.FunctionDeclaration(
                name=callable_.__name__,
                description=callable_.__doc__,
                parameters_json_schema={"type": "object", "properties": {}},
            )
        )
        mock_from_provider_name.return_value = llm_client

        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            grounding="text",
            step_summarizer=None,
        )

        mock_from_provider_name.assert_called_once_with(expected_provider, max_retries=1)
        self.assertEqual(agent._llm_client.provider_name, expected_provider)

    def test_generate_content_config_tools_match_expected_structure(self):
        tools = self.get_tools()
        first_tool = tools[0]
        second_tool = tools[1]
        if first_tool.computer_use is None:
            self.fail("Expected computer_use tool")
        if second_tool.function_declarations is None:
            self.fail("Expected function declarations tool")

        self.assertEqual(len(tools), 2)
        self.assertEqual(
            first_tool.computer_use.environment,
            types.Environment.ENVIRONMENT_BROWSER,
        )
        self.assertEqual(
            first_tool.computer_use.excluded_predefined_functions,
            ["search"],
        )
        self.assertEqual(
            [declaration.name for declaration in second_tool.function_declarations],
            [
                "reload_page",
                "list_tabs",
                "switch_to_next_tab",
                "switch_to_previous_tab",
                "switch_to_tab",
                "close_current_tab",
            ],
        )


    def test_mixed_grounding_exposes_default_tab_recovery_tools(self):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            grounding="mixed",
            step_summarizer=None,
        )

        tools = agent._generate_content_config.tools
        if tools is None:
            self.fail("Expected generate content tools")
        declarations = tools[1].function_declarations
        if declarations is None:
            self.fail("Expected function declarations tool")

        declaration_names = [declaration.name for declaration in declarations]
        self.assertIn("check_by_ref", declaration_names)
        self.assertIn("list_tabs", declaration_names)
        self.assertIn("switch_to_tab", declaration_names)
        self.assertIn("close_current_tab", declaration_names)

    def test_text_grounding_exposes_ref_verification_tools(self):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            grounding="text",
            step_summarizer=None,
        )

        tools = agent._generate_content_config.tools
        if tools is None:
            self.fail("Expected generate content tools")
        declarations = tools[0].function_declarations
        if declarations is None:
            self.fail("Expected function declarations tool")

        declaration_names = [declaration.name for declaration in declarations]
        self.assertIn("check_by_ref", declaration_names)
        self.assertIn("wait_for_ref", declaration_names)
        self.assertIn("list_tabs", declaration_names)
        self.assertIn("switch_to_tab", declaration_names)
        self.assertIn("close_current_tab", declaration_names)
        self.assertNotIn("search", declaration_names)
        self.assertNotIn("get_accessibility_tree", declaration_names)

    def test_get_model_response_calls_llm_client(self):
        mock_response = MagicMock()
        self.mock_llm_client.generate_content.return_value = mock_response

        response = self.agent.get_model_response()

        self.assertIs(response, mock_response)
        self.mock_llm_client.generate_content.assert_called_once_with(
            model="test_model",
            contents=self.agent._contents,
            config=self.agent._generate_content_config,
        )

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_no_function_calls(self, mock_get_model_response):
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [types.Part(text="some reasoning")]
        mock_response.candidates = [mock_candidate]
        mock_get_model_response.return_value = mock_response

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        self.assertEqual(len(self.agent._contents), 2)
        self.assertEqual(self.agent._contents[1], mock_candidate.content)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_retries_empty_model_turn(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        mock_get_model_response.return_value = self.make_response([])

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.assertEqual([event["type"] for event in events][-2:], ["step_error", "step_complete"])
        self.assertEqual(events[-1]["status"], "retry")
        latest_message = agent.get_recent_messages(limit=1)[0]["text"] or ""
        self.assertIn("previous response was empty", latest_message)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_agent_loop_fails_after_repeated_empty_model_turns(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        mock_get_model_response.return_value = self.make_response([])

        with self.assertRaisesRegex(RuntimeError, "no text or tool calls"):
            agent.agent_loop()

        self.assertEqual(mock_get_model_response.call_count, 3)
        self.assertIsNone(agent.final_reasoning)

    def test_agent_loop_enforces_total_step_budget(self):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
            max_total_steps=2,
        )

        with patch.object(agent, "run_one_iteration", return_value="CONTINUE") as mock_iteration:
            with self.assertRaisesRegex(RuntimeError, "Exceeded max total steps"):
                agent.agent_loop()

        self.assertEqual(mock_iteration.call_count, 2)
        self.assertEqual(events[-1]["type"], "step_error")
        self.assertIn("Exceeded max total steps", events[-1]["error_message"])

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_retries_on_malformed_function_call(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        mock_get_model_response.return_value = self.make_response(
            [],
            finish_reason=types.FinishReason.MALFORMED_FUNCTION_CALL,
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.assertEqual(len(agent._contents), 2)
        self.assertEqual(agent._contents[1].parts, [])
        self.assertEqual(
            [event["type"] for event in events],
            [
                "step_started",
                "model_response",
                "reasoning_extracted",
                "function_calls_extracted",
                "step_error",
            ],
        )
        self.assertEqual(events[-1]["error_message"], "Malformed function call.")

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_with_function_call(self, mock_get_model_response):
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        function_call = types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        mock_candidate.content.parts = [types.Part(function_call=function_call)]
        mock_response.candidates = [mock_candidate]
        mock_get_model_response.return_value = mock_response

        mock_env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.navigate.return_value = mock_env_state

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_called_once_with("https://example.com")
        self.assertEqual(len(self.agent._contents), 3)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_retries_unsupported_function_call(
        self,
        mock_get_model_response,
    ):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        unsupported_call = types.FunctionCall(
            id="chatcmpl-tool-a28e2a0058d8c7b4",
            name="SUBGOAL_DONE",
            args={},
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=unsupported_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_not_called()
        self.assertEqual(len(agent._contents), 2)
        retry_prompt = agent._contents[-1].parts[0].text or ""
        self.assertEqual(agent._contents[-1].role, "user")
        self.assertIn("unsupported function call", retry_prompt.lower())
        self.assertIn("SUBGOAL_DONE", retry_prompt)
        self.assertNotIn(
            unsupported_call,
            [
                part.function_call
                for content in agent._contents
                for part in (content.parts or [])
            ],
        )
        self.assertEqual(events[-1]["type"], "step_complete")
        self.assertEqual(events[-1]["status"], "retry")
        self.assertIn("Unsupported function", events[-2]["error_message"])

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_env_state_function_response(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        function_call = types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )
        self.mock_browser_computer.navigate.return_value = EnvState(
            screenshot=b"screenshot",
            url="https://example.com",
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        tool_turn = agent._contents[-1]
        function_response = self.get_function_response(tool_turn)
        if function_response.parts is None:
            self.fail("Expected screenshot parts on browser tool response")
        inline_data = function_response.parts[0].inline_data
        if inline_data is None:
            self.fail("Expected inline screenshot data")
        self.assertEqual(function_response.name, "navigate")
        self.assertEqual(function_response.response, {"url": "https://example.com"})
        self.assertEqual(inline_data.mime_type, "image/png")
        self.assertEqual(inline_data.data, b"screenshot")
        self.assertEqual(events[4]["type"], "action_executed")
        self.assertEqual(events[4]["artifacts"], self.mock_browser_computer.latest_artifact_metadata.return_value)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_dict_function_response(self, mock_get_model_response):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            custom_functions=[multiply_numbers],
        )
        function_call = types.FunctionCall(
            name=multiply_numbers.__name__,
            args={"x": 2, "y": 3},
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        tool_turn = agent._contents[-1]
        function_response = self.get_function_response(tool_turn)
        self.assertEqual(function_response.name, multiply_numbers.__name__)
        self.assertEqual(function_response.response, {"result": 6})
        self.assertIsNone(function_response.parts)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_skips_stale_browser_action_after_env_state(
        self,
        mock_get_model_response,
    ):
        first_call = types.FunctionCall(
            id="call-first",
            name="navigate",
            args={"url": "https://example.com/one"},
        )
        stale_call = types.FunctionCall(
            id="call-stale",
            name="navigate",
            args={"url": "https://example.com/two"},
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(function_call=first_call),
                types.Part(function_call=stale_call),
            ]
        )
        self.mock_browser_computer.navigate.return_value = EnvState(
            screenshot=b"first",
            url="https://example.com/one",
        )

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_called_once_with("https://example.com/one")
        tool_turn = self.agent._contents[-1]
        responses = [
            part.function_response
            for part in (tool_turn.parts or [])
            if part.function_response is not None
        ]
        self.assertEqual([response.id for response in responses], ["call-first", "call-stale"])
        self.assertEqual(responses[0].response, {"url": "https://example.com/one"})
        self.assertEqual(responses[1].response["status"], "reobserve_required")
        self.assertEqual(responses[1].response["error_type"], "ReobserveRequired")

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_batches_dict_tools_before_browser_state(
        self,
        mock_get_model_response,
    ):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            custom_functions=[multiply_numbers],
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(
                    function_call=types.FunctionCall(
                        name=multiply_numbers.__name__,
                        args={"x": 2, "y": 3},
                    )
                ),
                types.Part(
                    function_call=types.FunctionCall(
                        name="navigate",
                        args={"url": "https://example.com"},
                    )
                ),
            ]
        )
        self.mock_browser_computer.navigate.return_value = EnvState(
            screenshot=b"screenshot",
            url="https://example.com",
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_called_once_with("https://example.com")
        tool_turn = agent._contents[-1]
        responses = [
            part.function_response
            for part in (tool_turn.parts or [])
            if part.function_response is not None
        ]
        self.assertEqual(responses[0].response, {"result": 6})
        self.assertEqual(responses[1].response, {"url": "https://example.com"})

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_tool_execution_errors(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        function_call = types.FunctionCall(name="navigate", args={})
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_not_called()
        tool_turn = agent._contents[-1]
        function_response = self.get_function_response(tool_turn)
        self.assertEqual(function_response.name, "navigate")
        self.assertEqual(function_response.response["status"], "error")
        self.assertEqual(function_response.response["tool_name"], "navigate")
        self.assertEqual(function_response.response["error_type"], "KeyError")
        error_response_message = function_response.response.get("error") or ""
        self.assertIn("Tool execution failed for navigate", error_response_message)
        step_errors = [event for event in events if event["type"] == "step_error"]
        self.assertEqual(len(step_errors), 1)
        step_error_message = step_errors[0].get("error_message") or ""
        self.assertIn("Tool execution failed for navigate", step_error_message)


    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_tab_action_errors(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        self.mock_browser_computer.close_current_tab.side_effect = ValueError(
            "Cannot close the only open tab"
        )
        function_call = types.FunctionCall(name="close_current_tab", args={})
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        function_response = self.get_function_response(agent._contents[-1])
        self.assertEqual(function_response.name, "close_current_tab")
        self.assertEqual(function_response.response["status"], "error")
        self.assertEqual(function_response.response["error_type"], "ValueError")
        self.assertIn("Cannot close the only open tab", function_response.response["error"])
        step_errors = [event for event in events if event["type"] == "step_error"]
        self.assertEqual(len(step_errors), 1)
        self.assertIn("close_current_tab", step_errors[0]["error_message"])

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_malformed_tool_argument_errors(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        function_call = types.FunctionCall(
            name="navigate",
            args={
                TOOL_ARGUMENT_ERROR_KEY: {
                    "status": "error",
                    "tool_name": "navigate",
                    "error_type": "JSONDecodeError",
                    "error": "Malformed tool arguments JSON for navigate: bad payload",
                }
            },
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.navigate.assert_not_called()
        function_response = self.get_function_response(agent._contents[-1])
        self.assertEqual(function_response.response["status"], "error")
        self.assertEqual(function_response.response["error_type"], "JSONDecodeError")
        self.assertEqual(function_response.response["tool_name"], "navigate")
        error_message = function_response.response.get("error") or ""
        self.assertIn("Malformed tool arguments JSON", error_message)
        step_errors = [event for event in events if event["type"] == "step_error"]
        self.assertEqual(len(step_errors), 1)
        step_error_message = step_errors[0].get("error_message") or ""
        self.assertIn("Malformed tool arguments JSON", step_error_message)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_enriches_browser_metadata_with_reasoning(
        self,
        mock_get_model_response,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_dir = Path(tmp_dir)
            self.write_metadata_file(
                history_dir,
                "step-0001.json",
                step=1,
                url="https://example.com",
            )
            self.mock_browser_computer.history_dir.return_value = history_dir
            self.mock_browser_computer.latest_artifact_metadata.return_value = {
                "step": 1,
                "timestamp": 123.45,
                "url": "https://example.com",
                "html_path": "step-0001.html",
                "screenshot_path": "step-0001.png",
                "metadata_path": "step-0001.json",
            }
            self.mock_browser_computer.navigate.return_value = EnvState(
                screenshot=b"screenshot",
                url="https://example.com",
            )
            mock_get_model_response.return_value = self.make_response(
                [
                    types.Part(text="I should inspect the page before answering."),
                    types.Part(
                        function_call=types.FunctionCall(
                            name="navigate",
                            args={"url": "https://example.com"},
                        )
                    ),
                ]
            )

            result = self.agent.run_one_iteration()

            self.assertEqual(result, "CONTINUE")
            metadata = json.loads((history_dir / "step-0001.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["step"], 1)
            self.assertEqual(metadata["url"], "https://example.com")
            self.assertEqual(metadata["action"], {"name": "navigate", "args": {"url": "https://example.com"}})
            self.assertEqual(metadata["action_summary"], "Navigated to https://example.com")
            self.assertEqual(metadata["reason"], "I should inspect the page before answering.")
            self.assertEqual(
                metadata["reasoning_text"],
                "I should inspect the page before answering.",
            )
            self.assertEqual(metadata["summary_source"], "app_derived")
            self.assertEqual(metadata["model_step_id"], 1)
            self.assertEqual(metadata["function_call_index_within_step"], 1)

    def test_build_persisted_action_metadata_uses_fallback_reason_when_reasoning_missing(self):
        metadata = ActionReviewService(query="test query").build_persisted_action_metadata(
            step_id=3,
            function_call_index=1,
            function_call=types.FunctionCall(
                name="navigate",
                args={"url": "https://example.com"},
            ),
            reasoning=None,
        )

        self.assertEqual(metadata["action_summary"], "Navigated to https://example.com")
        self.assertEqual(metadata["reason"], "Needed to open https://example.com.")
        self.assertIsNone(metadata["reasoning_text"])
        self.assertEqual(metadata["model_step_id"], 3)
        self.assertEqual(metadata["function_call_index_within_step"], 1)

    def test_record_step_review_metadata_preserves_ambiguity_across_multiple_calls(self):
        self.agent._record_step_review_metadata(
            step_id=1,
            review_metadata={
                "phase_id": "phase-input",
                "phase_label": "입력 및 조작",
                "phase_summary": None,
                "action_summary": "Typed text at (10, 20)",
                "reason": "Needed to enter text into the page.",
                "summary_source": "app_derived",
                "user_visible_label": "Typed text at (10, 20)",
                "ambiguity_flag": True,
                "ambiguity_type": "typed_text_not_in_query",
                "ambiguity_message": "Entered text was not explicitly present in the original request.",
                "review_evidence": ["typed_text_not_in_query"],
                "a11y_path": "step-0001.a11y.yaml",
                "verification_items": [{"id": "v1"}],
            },
        )
        self.agent._record_step_review_metadata(
            step_id=1,
            review_metadata={
                "phase_id": "phase-navigation",
                "phase_label": "페이지 이동",
                "phase_summary": None,
                "action_summary": "Navigated to https://example.com",
                "reason": "Needed to open https://example.com.",
                "summary_source": "app_derived",
                "user_visible_label": "Navigated to https://example.com",
                "ambiguity_flag": False,
                "ambiguity_type": None,
                "ambiguity_message": None,
                "review_evidence": [],
                "a11y_path": None,
                "verification_items": [],
            },
        )

        review_metadata = self.agent._step_review_metadata[1]
        self.assertTrue(review_metadata["ambiguity_flag"])
        self.assertEqual(review_metadata["ambiguity_type"], "typed_text_not_in_query")
        self.assertEqual(review_metadata["review_evidence"], ["typed_text_not_in_query"])
        self.assertEqual(review_metadata["verification_items"], [{"id": "v1"}])
        self.assertEqual(review_metadata["phase_id"], "phase-input")
        self.assertEqual(review_metadata["action_summary"], "Typed text at (10, 20)")
        self.assertEqual(review_metadata["reason"], "Needed to enter text into the page.")

    def test_build_review_metadata_for_action_creates_verification_item_for_typed_text_ambiguity(self):
        review_metadata = ActionReviewService(query="test query").build_review_metadata_for_action(
            step_id=1,
            function_call_index=1,
            function_call=types.FunctionCall(
                name="type_text_at",
                args={"x": 10, "y": 20, "text": "business class"},
            ),
            reasoning="I need to fill the seat class field.",
            artifacts={
                "a11y_path": "step-0001.a11y.yaml",
                "url": "https://example.com/search",
            },
        )

        self.assertTrue(review_metadata["ambiguity_flag"])
        self.assertEqual(review_metadata["ambiguity_type"], "typed_text_not_in_query")
        self.assertEqual(review_metadata["a11y_path"], "step-0001.a11y.yaml")
        self.assertEqual(len(review_metadata["verification_items"]), 1)
        verification_item = review_metadata["verification_items"][0]
        self.assertEqual(verification_item["source_step_id"], 1)
        self.assertEqual(verification_item["ambiguity_type"], "typed_text_not_in_query")
        self.assertEqual(verification_item["a11y_path"], "step-0001.a11y.yaml")

    def test_resolve_metadata_file_path_supports_relative_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_dir = Path(tmp_dir)
            absolute_metadata_path = history_dir / "absolute.json"
            absolute_metadata_path.write_text("{}", encoding="utf-8")
            self.mock_browser_computer.history_dir.return_value = history_dir

            relative_path = self.agent._resolve_metadata_file_path(
                {"metadata_path": "step-0001.json"}
            )
            absolute_path = self.agent._resolve_metadata_file_path(
                {"metadata_path": str(absolute_metadata_path)}
            )

            self.assertEqual(relative_path, history_dir / "step-0001.json")
            self.assertEqual(absolute_path, absolute_metadata_path)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_skips_metadata_for_stale_same_turn_browser_action(
        self,
        mock_get_model_response,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_dir = Path(tmp_dir)
            self.write_metadata_file(
                history_dir,
                "step-0001.json",
                step=1,
                url="https://example.com/one",
            )
            self.write_metadata_file(
                history_dir,
                "step-0002.json",
                step=2,
                url="https://example.com/two",
            )
            self.mock_browser_computer.history_dir.return_value = history_dir
            self.mock_browser_computer.latest_artifact_metadata.side_effect = [
                {
                    "step": 1,
                    "timestamp": 123.45,
                    "url": "https://example.com/one",
                    "html_path": "step-0001.html",
                    "screenshot_path": "step-0001.png",
                    "metadata_path": "step-0001.json",
                },
                {
                    "step": 2,
                    "timestamp": 234.56,
                    "url": "https://example.com/two",
                    "html_path": "step-0002.html",
                    "screenshot_path": "step-0002.png",
                    "metadata_path": "step-0002.json",
                },
            ]
            self.mock_browser_computer.navigate.side_effect = [
                EnvState(screenshot=b"first", url="https://example.com/one"),
                EnvState(screenshot=b"second", url="https://example.com/two"),
            ]
            mock_get_model_response.return_value = self.make_response(
                [
                    types.Part(text="Inspect both pages."),
                    types.Part(
                        function_call=types.FunctionCall(
                            name="navigate",
                            args={"url": "https://example.com/one"},
                        )
                    ),
                    types.Part(
                        function_call=types.FunctionCall(
                            name="navigate",
                            args={"url": "https://example.com/two"},
                        )
                    ),
                ]
            )

            result = self.agent.run_one_iteration()

            self.assertEqual(result, "CONTINUE")
            first_metadata = json.loads((history_dir / "step-0001.json").read_text(encoding="utf-8"))
            second_metadata = json.loads((history_dir / "step-0002.json").read_text(encoding="utf-8"))
            self.assertEqual(first_metadata["function_call_index_within_step"], 1)
            self.assertEqual(first_metadata["model_step_id"], 1)
            self.assertEqual(first_metadata["action"]["args"], {"url": "https://example.com/one"})
            self.assertNotIn("function_call_index_within_step", second_metadata)
            self.assertNotIn("model_step_id", second_metadata)
            self.assertEqual(self.mock_browser_computer.navigate.call_count, 1)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_custom_function_result_skips_metadata_enrichment(
        self,
        mock_get_model_response,
    ):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            custom_functions=[multiply_numbers],
        )
        function_call = types.FunctionCall(
            name=multiply_numbers.__name__,
            args={"x": 2, "y": 3},
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(text="Need the product."),
                types.Part(function_call=function_call),
            ]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        self.mock_browser_computer.latest_artifact_metadata.assert_not_called()
        self.mock_browser_computer.history_dir.assert_not_called()

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_prunes_old_screenshots(self, mock_get_model_response):
        oldest_turn = self.make_screenshot_turn("navigate", b"oldest")
        middle_turn = self.make_screenshot_turn("navigate", b"middle")
        newest_turn = self.make_screenshot_turn("navigate", b"newest")
        self.agent._contents.extend([oldest_turn, middle_turn, newest_turn])
        self.mock_browser_computer.navigate.return_value = EnvState(
            screenshot=b"fresh",
            url="https://example.com/fresh",
        )
        function_call = types.FunctionCall(name="navigate", args={"url": "https://example.com/fresh"})
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        oldest_parts = oldest_turn.parts
        middle_parts = middle_turn.parts
        newest_parts = newest_turn.parts
        latest_parts = self.agent._contents[-1].parts
        if oldest_parts is None:
            self.fail("Expected screenshot parts on oldest turn")
        if middle_parts is None:
            self.fail("Expected screenshot parts on middle turn")
        if newest_parts is None:
            self.fail("Expected screenshot parts on newest turn")
        if latest_parts is None:
            self.fail("Expected screenshot parts on latest turn")

        oldest_response = oldest_parts[0].function_response
        middle_response = middle_parts[0].function_response
        newest_response = newest_parts[0].function_response
        latest_response = latest_parts[0].function_response
        if oldest_response is None:
            self.fail("Expected function response on oldest turn")
        if middle_response is None:
            self.fail("Expected function response on middle turn")
        if newest_response is None:
            self.fail("Expected function response on newest turn")
        if latest_response is None:
            self.fail("Expected function response on latest turn")

        self.assertIsNone(oldest_response.parts)
        self.assertIsNotNone(middle_response.parts)
        self.assertIsNotNone(newest_response.parts)
        self.assertIsNotNone(latest_response.parts)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_terminates_when_safety_confirmation_rejected(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        function_call = types.FunctionCall(
            name="navigate",
            args={
                "url": "https://example.com",
                "safety_decision": {
                    "decision": "require_confirmation",
                    "explanation": "Need approval.",
                },
            },
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        with patch.object(
            agent,
            "_get_safety_confirmation",
            return_value="TERMINATE",
        ):
            result = agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        self.mock_browser_computer.navigate.assert_not_called()
        self.assertEqual(
            [event["type"] for event in events],
            [
                "step_started",
                "model_response",
                "reasoning_extracted",
                "function_calls_extracted",
                "step_complete",
            ],
        )
        self.assertEqual(
            events[-1]["final_reasoning"],
            "Terminated after safety confirmation rejection.",
        )

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_uses_non_interactive_safety_callback(self, mock_get_model_response):
        decisions = []
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
            safety_confirmation_callback=lambda safety: decisions.append(safety) or "TERMINATE",
        )
        function_call = types.FunctionCall(
            name="navigate",
            args={
                "url": "https://example.com",
                "safety_decision": {
                    "decision": "require_confirmation",
                    "explanation": "Need approval.",
                },
            },
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        self.assertEqual(decisions[0]["explanation"], "Need approval.")
        self.mock_browser_computer.navigate.assert_not_called()
        self.assertIn("safety_confirmation_required", [event["type"] for event in events])

    def test_append_user_message(self):
        self.agent.append_user_message("follow up")

        recent_messages = self.agent.get_recent_messages(limit=2)

        self.assertEqual(
            recent_messages,
            [
                {"role": "user", "text": "test query"},
                {"role": "user", "text": "follow up"},
            ],
        )

    def test_conversation_context_is_included_in_initial_prompt(self):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="16 Pro price too",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            conversation_context="User previously asked for iPhone 17 Pro price.",
        )

        recent_messages = agent.get_recent_messages(limit=1)
        initial_text = recent_messages[0]["text"] or ""

        self.assertEqual(len(recent_messages), 1)
        self.assertEqual(recent_messages[0]["role"], "user")
        self.assertIn("Conversation memory from previous tasks:", initial_text)
        self.assertIn("User previously asked for iPhone 17 Pro price.", initial_text)
        self.assertIn("Current user task:\n16 Pro price too", initial_text)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_emits_step_events(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [types.Part(text="some reasoning")]
        mock_candidate.finish_reason = None
        mock_response.candidates = [mock_candidate]
        mock_get_model_response.return_value = mock_response

        result = agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        self.assertEqual(
            [event["type"] for event in events],
            [
                "step_started",
                "model_response",
                "reasoning_extracted",
                "function_calls_extracted",
                "review_metadata_extracted",
                "step_complete",
            ],
        )
        self.assertEqual(events[-1]["final_reasoning"], "some reasoning")
        self.assertEqual(events[-2]["phase_id"], "phase-complete")

    def test_agent_loop_with_subgoals_emits_aggregate_final_result(self):
        events = []
        subgoals = [
            Subgoal(id=1, description="Open example", success_criteria="Example is open"),
            Subgoal(id=2, description="Summarize page", success_criteria="Summary is ready"),
        ]
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
            subgoals=subgoals,
        )

        with patch.object(
            agent,
            "_run_subgoal_loop",
            side_effect=[
                ("done", "SUBGOAL_DONE: opened example.com"),
                ("done", "SUBGOAL_DONE: summarized page"),
            ],
        ):
            agent.agent_loop()

        final_reasoning = agent.final_reasoning or ""
        self.assertIsNotNone(agent.final_reasoning)
        self.assertIn("All planner subgoals completed.", final_reasoning)
        self.assertIn("[1] Open example: SUBGOAL_DONE: opened example.com", final_reasoning)
        self.assertIn("[2] Summarize page: SUBGOAL_DONE: summarized page", final_reasoning)
        self.assertEqual(events[-2]["type"], "review_metadata_extracted")
        self.assertEqual(events[-2]["phase_id"], "phase-complete")
        self.assertEqual(events[-1]["type"], "step_complete")
        self.assertEqual(events[-1]["final_reasoning"], agent.final_reasoning)

    def test_agent_loop_with_subgoals_enforces_subgoal_budget(self):
        events = []
        subgoals = [
            Subgoal(id=1, description="Open example", success_criteria="Example is open"),
            Subgoal(id=2, description="Search page", success_criteria="Search is done"),
            Subgoal(id=3, description="Summarize page", success_criteria="Summary is ready"),
        ]
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
            subgoals=subgoals,
            max_subgoals=2,
        )

        with patch.object(agent, "_run_subgoal_loop") as mock_subgoal_loop:
            with self.assertRaisesRegex(RuntimeError, "Exceeded max subgoals"):
                agent.agent_loop()

        mock_subgoal_loop.assert_not_called()
        self.assertEqual(events[-1]["type"], "step_error")
        self.assertIn("Exceeded max subgoals", events[-1]["error_message"])

    def test_agent_loop_with_subgoals_enforces_total_step_budget(self):
        events = []
        subgoals = [
            Subgoal(id=1, description="Open example", success_criteria="Example is open"),
        ]
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
            subgoals=subgoals,
            max_steps_per_subgoal=5,
            max_total_steps=2,
        )

        with patch.object(agent, "run_one_iteration", return_value="CONTINUE") as mock_iteration:
            with self.assertRaisesRegex(RuntimeError, "Exceeded max total steps"):
                agent.agent_loop()

        self.assertEqual(mock_iteration.call_count, 2)
        self.assertEqual(events[-1]["type"], "step_error")
        self.assertIn("Exceeded max total steps", events[-1]["error_message"])

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_subgoal_loop_retries_missing_final_reasoning_before_failing(
        self,
        mock_get_model_response,
    ):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            max_steps_per_subgoal=3,
        )
        mock_get_model_response.side_effect = [
            self.make_response([]),
            self.make_response([types.Part(text="SUBGOAL_DONE: verified page state")]),
        ]

        result, reason = agent._run_subgoal_loop(
            Subgoal(id=3, description="Verify page", success_criteria="Page verified")
        )

        self.assertEqual(result, "done")
        self.assertEqual(reason, "SUBGOAL_DONE: verified page state")
        self.assertEqual(mock_get_model_response.call_count, 2)
        retry_message = agent.get_recent_messages(limit=2)[0]["text"] or ""
        self.assertIn(
            "without the required SUBGOAL_DONE: or SUBGOAL_FAILED: marker",
            retry_message,
        )

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_subgoal_loop_retries_plain_final_text_for_required_marker(
        self,
        mock_get_model_response,
    ):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            max_steps_per_subgoal=3,
        )
        mock_get_model_response.side_effect = [
            self.make_response([types.Part(text="The page is verified.")]),
            self.make_response([types.Part(text="SUBGOAL_DONE: the page is verified")]),
        ]

        result, reason = agent._run_subgoal_loop(
            Subgoal(id=3, description="Verify page", success_criteria="Page verified")
        )

        self.assertEqual(result, "done")
        self.assertEqual(reason, "SUBGOAL_DONE: the page is verified")
        self.assertEqual(mock_get_model_response.call_count, 2)

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_subgoal_loop_reports_empty_final_status_after_retry_budget(
        self,
        mock_get_model_response,
    ):
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            step_summarizer=None,
            max_steps_per_subgoal=2,
        )
        mock_get_model_response.side_effect = [
            self.make_response([]),
            self.make_response([]),
        ]

        result, reason = agent._run_subgoal_loop(
            Subgoal(id=3, description="Verify page", success_criteria="Page verified")
        )

        self.assertEqual(result, "failed")
        self.assertEqual(
            reason,
            "Subgoal 3 did not produce a final status message after 2 step(s).",
        )

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_builds_final_result_summary_for_chat(self, mock_get_model_response):
        events = []
        step_summarizer = MagicMock()
        step_summarizer.summarize_final_result.return_value = (
            "EXAONE 4.5 Hugging Face 페이지를 찾았습니다."
        )
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="exaone 4.5 huggingface 찾아줘",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=step_summarizer,
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(
                    text="I have evaluated the screenshot. Waiting again worked!",
                    thought=True,
                ),
                types.Part(
                    text=(
                        "I have found the page for exaone 4.5 "
                        "(LGAI-EXAONE/EXAONE-4.5-33B) on Hugging Face."
                    )
                ),
            ]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        review_event = next(
            event for event in events if event["type"] == "review_metadata_extracted"
        )
        self.assertEqual(
            review_event["final_result_summary"],
            "EXAONE 4.5 Hugging Face 페이지를 찾았습니다.",
        )
        step_summarizer.summarize_final_result.assert_called_once()

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_final_result_summary_falls_back_to_visible_text(
        self,
        mock_get_model_response,
    ):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="exaone 4.5 huggingface 찾아줘",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(
                    text="I have evaluated the screenshot. Waiting again worked!",
                    thought=True,
                ),
                types.Part(text="EXAONE 4.5 Hugging Face 페이지를 찾았습니다."),
            ]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "COMPLETE")
        review_event = next(
            event for event in events if event["type"] == "review_metadata_extracted"
        )
        self.assertEqual(
            review_event["final_result_summary"],
            "EXAONE 4.5 Hugging Face 페이지를 찾았습니다.",
        )

    @patch("agents.actor_agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_emits_runtime_phase_metadata_for_action_steps(
        self,
        mock_get_model_response,
    ):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="visit example",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
            step_summarizer=None,
        )
        self.mock_browser_computer.latest_artifact_metadata.return_value = {
            "step": 1,
            "timestamp": 123.45,
            "url": "https://example.com",
            "html_path": "step-0001.html",
            "screenshot_path": "step-0001.png",
            "metadata_path": "step-0001.json",
        }
        self.mock_browser_computer.navigate.return_value = EnvState(
            screenshot=b"screenshot",
            url="https://example.com",
        )
        mock_get_model_response.return_value = self.make_response(
            [
                types.Part(text="Open the destination page."),
                types.Part(
                    function_call=types.FunctionCall(
                        name="navigate",
                        args={"url": "https://example.com"},
                    )
                ),
            ]
        )

        result = agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        review_event = next(
            event for event in events if event["type"] == "review_metadata_extracted"
        )
        self.assertEqual(review_event["phase_id"], "phase-navigation")
        self.assertEqual(review_event["phase_label"], "페이지 이동")
        self.assertEqual(review_event["phase_summary"], "Open the destination page.")
        self.assertEqual(review_event["action_summary"], "Navigated to https://example.com")
        self.assertEqual(review_event["reason"], "Open the destination page.")
        self.assertEqual(review_event["summary_source"], "app_derived")
        self.assertEqual(review_event["user_visible_label"], "Navigated to https://example.com")


if __name__ == "__main__":
    unittest.main()
