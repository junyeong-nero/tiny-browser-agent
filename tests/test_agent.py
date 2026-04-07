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
from unittest.mock import MagicMock, patch
from google.genai import types
from agent import BrowserAgent, multiply_numbers
from computers import EnvState
from llm.client import LLMClient


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

    def test_multiply_numbers(self):
        self.assertEqual(multiply_numbers(2, 3), {"result": 6})

    def test_automatic_function_calling_is_disabled(self):
        self.assertTrue(
            self.agent._generate_content_config.automatic_function_calling.disable
        )

    def test_handle_action_open_web_browser(self):
        action = types.FunctionCall(name="open_web_browser", args={})
        self.agent.handle_action(action)
        self.mock_browser_computer.open_web_browser.assert_called_once()

    def test_handle_action_click_at(self):
        action = types.FunctionCall(name="click_at", args={"x": 100, "y": 200})
        self.agent.handle_action(action)
        self.mock_browser_computer.click_at.assert_called_once_with(x=100, y=200)

    def test_handle_action_type_text_at(self):
        action = types.FunctionCall(name="type_text_at", args={"x": 100, "y": 200, "text": "hello"})
        self.agent.handle_action(action)
        self.mock_browser_computer.type_text_at.assert_called_once_with(
            x=100, y=200, text="hello", press_enter=False, clear_before_typing=True
        )

    def test_handle_action_scroll_document(self):
        action = types.FunctionCall(name="scroll_document", args={"direction": "down"})
        self.agent.handle_action(action)
        self.mock_browser_computer.scroll_document.assert_called_once_with("down")

    def test_handle_action_navigate(self):
        action = types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        self.agent.handle_action(action)
        self.mock_browser_computer.navigate.assert_called_once_with("https://example.com")

    def test_handle_action_unknown_function(self):
        action = types.FunctionCall(name="unknown_function", args={})
        with self.assertRaises(ValueError):
            self.agent.handle_action(action)

    def test_denormalize_x(self):
        self.assertEqual(self.agent.denormalize_x(500), 500)

    def test_denormalize_y(self):
        self.assertEqual(self.agent.denormalize_y(500), 500)

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

    @patch("agent.BrowserAgent.get_model_response")
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

    @patch("agent.BrowserAgent.get_model_response")
    @patch("agent.BrowserAgent.handle_action")
    def test_run_one_iteration_with_function_call(self, mock_handle_action, mock_get_model_response):
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        function_call = types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        mock_candidate.content.parts = [types.Part(function_call=function_call)]
        mock_response.candidates = [mock_candidate]
        mock_get_model_response.return_value = mock_response

        mock_env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        mock_handle_action.return_value = mock_env_state

        result = self.agent.run_one_iteration()

        self.assertEqual(result, "CONTINUE")
        mock_handle_action.assert_called_once_with(function_call)
        self.assertEqual(len(self.agent._contents), 3)

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

    @patch("agent.BrowserAgent.get_model_response")
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
