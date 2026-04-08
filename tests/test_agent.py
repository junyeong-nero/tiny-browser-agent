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

import unittest
from typing import cast
from unittest.mock import MagicMock, patch
from google.genai import types
from src.agent import BrowserAgent, multiply_numbers
from src.computers.computer import EnvState
from src.llm.client import LLMClient


class TestBrowserAgent(unittest.TestCase):
    def setUp(self):
        self.mock_browser_computer = MagicMock()
        self.mock_browser_computer.screen_size.return_value = (1000, 1000)
        self.mock_browser_computer.latest_artifact_metadata.return_value = {
            "screenshot_path": "step-0001.png",
            "html_path": "step-0001.html",
            "metadata_path": "step-0001.json",
        }
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.mock_llm_client.build_function_declaration.return_value = types.FunctionDeclaration(
            name=multiply_numbers.__name__,
            description=multiply_numbers.__doc__,
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["x", "y"],
            },
        )
        self.agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
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

    def test_multiply_numbers(self):
        self.assertEqual(multiply_numbers(2, 3), {"result": 6})

    def test_automatic_function_calling_is_disabled(self):
        automatic_function_calling = self.agent._generate_content_config.automatic_function_calling
        if automatic_function_calling is None:
            self.fail("Expected automatic function calling config")
        self.assertTrue(automatic_function_calling.disable)

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
            [],
        )
        self.assertEqual(
            [declaration.name for declaration in second_tool.function_declarations],
            [multiply_numbers.__name__],
        )

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

    @patch("src.agent.BrowserAgent.get_model_response")
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

    @patch("src.agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_retries_on_malformed_function_call(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
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

    @patch("src.agent.BrowserAgent.get_model_response")
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

    @patch("src.agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_env_state_function_response(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
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

    @patch("src.agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_serializes_dict_function_response(self, mock_get_model_response):
        function_call = types.FunctionCall(
            name=multiply_numbers.__name__,
            args={"x": 2, "y": 3},
        )
        mock_get_model_response.return_value = self.make_response(
            [types.Part(function_call=function_call)]
        )

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        tool_turn = self.agent._contents[-1]
        function_response = self.get_function_response(tool_turn)
        self.assertEqual(function_response.name, multiply_numbers.__name__)
        self.assertEqual(function_response.response, {"result": 6})
        self.assertIsNone(function_response.parts)

    @patch("src.agent.BrowserAgent.get_model_response")
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

    @patch("src.agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_terminates_when_safety_confirmation_rejected(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
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

    @patch("src.agent.BrowserAgent.get_model_response")
    def test_run_one_iteration_emits_step_events(self, mock_get_model_response):
        events = []
        agent = BrowserAgent(
            browser_computer=self.mock_browser_computer,
            query="test query",
            model_name="test_model",
            llm_client=self.mock_llm_client,
            event_sink=events.append,
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
        self.assertEqual(events[-2]["phase_id"], "all-steps")


if __name__ == "__main__":
    unittest.main()
