import unittest
from unittest.mock import MagicMock

from google.genai import types

from agents.actor_agent import multiply_numbers
from browser import build_browser_action_functions, EnvState
from tool_executor import BrowserToolExecutor, prune_old_screenshot_parts


class TestBrowserToolExecutor(unittest.TestCase):
    def setUp(self):
        self.mock_browser_computer = MagicMock()
        self.mock_browser_computer.screen_size.return_value = (2000, 4000)
        self.mock_browser_computer.latest_artifact_metadata.return_value = {
            "screenshot_path": "step-0001.png",
            "html_path": "step-0001.html",
            "metadata_path": "step-0001.json",
            "a11y_path": "step-0001.a11y.yaml",
        }
        self.executor = BrowserToolExecutor(
            browser_computer=self.mock_browser_computer,
            custom_functions=[
                multiply_numbers,
                *build_browser_action_functions(self.mock_browser_computer),
            ],
        )

    def get_inline_data(
        self,
        function_response: types.FunctionResponse,
    ) -> types.FunctionResponseBlob:
        if function_response.parts is None:
            self.fail("Expected function response parts")
        inline_data = function_response.parts[0].inline_data
        if inline_data is None:
            self.fail("Expected inline data")
        return inline_data

    def test_execute_open_web_browser(self):
        env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.open_web_browser.return_value = env_state

        result = self.executor.execute(types.FunctionCall(name="open_web_browser", args={}))

        self.assertEqual(result, env_state)
        self.mock_browser_computer.open_web_browser.assert_called_once_with()

    def test_execute_click_at(self):
        self.executor.execute(types.FunctionCall(name="click_at", args={"x": 100, "y": 200}))

        self.mock_browser_computer.click_at.assert_called_once_with(x=200, y=800)

    def test_execute_hover_at(self):
        self.executor.execute(types.FunctionCall(name="hover_at", args={"x": 100, "y": 200}))

        self.mock_browser_computer.hover_at.assert_called_once_with(x=200, y=800)

    def test_execute_type_text_at_uses_default_flags(self):
        self.executor.execute(
            types.FunctionCall(name="type_text_at", args={"x": 100, "y": 200, "text": "hello"})
        )

        self.mock_browser_computer.type_text_at.assert_called_once_with(
            x=200,
            y=800,
            text="hello",
            press_enter=False,
            clear_before_typing=True,
        )

    def test_execute_scroll_document(self):
        self.executor.execute(types.FunctionCall(name="scroll_document", args={"direction": "down"}))

        self.mock_browser_computer.scroll_document.assert_called_once_with("down")

    def test_execute_wait_5_seconds(self):
        self.executor.execute(types.FunctionCall(name="wait_5_seconds", args={}))

        self.mock_browser_computer.wait_5_seconds.assert_called_once_with()

    def test_execute_go_back(self):
        self.executor.execute(types.FunctionCall(name="go_back", args={}))

        self.mock_browser_computer.go_back.assert_called_once_with()

    def test_execute_go_forward(self):
        self.executor.execute(types.FunctionCall(name="go_forward", args={}))

        self.mock_browser_computer.go_forward.assert_called_once_with()

    def test_execute_search(self):
        self.executor.execute(types.FunctionCall(name="search", args={}))

        self.mock_browser_computer.search.assert_called_once_with()

    def test_execute_navigate(self):
        self.executor.execute(
            types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        )

        self.mock_browser_computer.navigate.assert_called_once_with("https://example.com")

    def test_execute_key_combination(self):
        self.executor.execute(
            types.FunctionCall(name="key_combination", args={"keys": "Meta+Shift+P"})
        )

        self.mock_browser_computer.key_combination.assert_called_once_with(
            ["Meta", "Shift", "P"]
        )

    def test_execute_press_key_delegates_to_key_combination(self):
        env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.key_combination.return_value = env_state

        result = self.executor.execute(
            types.FunctionCall(name="press_key", args={"key": "Escape"})
        )

        self.mock_browser_computer.key_combination.assert_called_once_with(["Escape"])
        self.assertEqual(result, env_state)

    def test_execute_reload_page_delegates_to_browser_computer(self):
        env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.reload_page.return_value = env_state

        result = self.executor.execute(types.FunctionCall(name="reload_page", args={}))

        self.mock_browser_computer.reload_page.assert_called_once_with()
        self.assertEqual(result, env_state)

    def test_execute_upload_file_denormalizes_coordinates(self):
        env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.upload_file.return_value = env_state

        result = self.executor.execute(
            types.FunctionCall(
                name="upload_file",
                args={"x": 100, "y": 200, "path": "/tmp/file.txt"},
            )
        )

        self.mock_browser_computer.upload_file.assert_called_once_with(
            x=200, y=800, path="/tmp/file.txt"
        )
        self.assertEqual(result, env_state)

    def test_execute_get_accessibility_tree_returns_dict(self):
        tree_payload = {
            "tree": "- body\n  - button: Continue",
            "url": "https://example.com",
            "source": "dom_accessibility_outline",
            "status": "captured",
            "error": None,
        }
        self.mock_browser_computer.get_accessibility_tree.return_value = tree_payload

        result = self.executor.execute(
            types.FunctionCall(name="get_accessibility_tree", args={})
        )

        self.mock_browser_computer.get_accessibility_tree.assert_called_once_with()
        self.assertEqual(result, tree_payload)

    def test_execute_drag_and_drop(self):
        self.executor.execute(
            types.FunctionCall(
                name="drag_and_drop",
                args={
                    "x": 100,
                    "y": 200,
                    "destination_x": 300,
                    "destination_y": 400,
                },
            )
        )

        self.mock_browser_computer.drag_and_drop.assert_called_once_with(
            x=200,
            y=800,
            destination_x=600,
            destination_y=1600,
        )

    def test_denormalize_x(self):
        self.assertEqual(self.executor.denormalize_x(500), 1000)

    def test_denormalize_y(self):
        self.assertEqual(self.executor.denormalize_y(500), 2000)

    def test_execute_scroll_at_denormalizes_coordinates_and_magnitude(self):
        self.executor.execute(
            types.FunctionCall(
                name="scroll_at",
                args={"x": 100, "y": 200, "direction": "down", "magnitude": 500},
            )
        )

        self.mock_browser_computer.scroll_at.assert_called_once_with(
            x=200,
            y=800,
            direction="down",
            magnitude=2000,
        )

    def test_execute_custom_function(self):
        result = self.executor.execute(
            types.FunctionCall(name=multiply_numbers.__name__, args={"x": 2, "y": 3})
        )

        self.assertEqual(result, {"result": 6})

    def test_execute_call_includes_artifacts_for_env_state(self):
        env_state = EnvState(screenshot=b"screenshot", url="https://example.com")
        self.mock_browser_computer.navigate.return_value = env_state

        executed_call = self.executor.execute_call(
            types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        )

        self.assertEqual(executed_call.result, env_state)
        self.assertEqual(
            executed_call.artifacts,
            self.mock_browser_computer.latest_artifact_metadata.return_value,
        )

    def test_serialize_function_response_for_env_state(self):
        executed_call = self.executor.execute_call(
            types.FunctionCall(name="navigate", args={"url": "https://example.com"})
        )
        executed_call = executed_call.__class__(
            function_call=executed_call.function_call,
            result=EnvState(screenshot=b"screenshot", url="https://example.com"),
            artifacts=executed_call.artifacts,
        )

        function_response = self.executor.serialize_function_response(
            executed_call,
            extra_response_fields={"safety_acknowledgement": "true"},
        )

        self.assertEqual(function_response.name, "navigate")
        self.assertEqual(
            function_response.response,
            {
                "url": "https://example.com",
                "safety_acknowledgement": "true",
            },
        )
        inline_data = self.get_inline_data(function_response)
        self.assertEqual(inline_data.mime_type, "image/png")
        self.assertEqual(inline_data.data, b"screenshot")

    def test_serialize_function_response_for_dict(self):
        executed_call = self.executor.execute_call(
            types.FunctionCall(name=multiply_numbers.__name__, args={"x": 2, "y": 3})
        )

        function_response = self.executor.serialize_function_response(executed_call)

        self.assertEqual(function_response.name, multiply_numbers.__name__)
        self.assertEqual(function_response.response, {"result": 6})
        self.assertIsNone(function_response.parts)

    def test_execute_unknown_function_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.executor.execute(types.FunctionCall(name="unknown_function", args={}))


class TestPruneOldScreenshotParts(unittest.TestCase):
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

    def get_function_response(self, content: types.Content) -> types.FunctionResponse:
        if content.parts is None:
            self.fail("Expected content parts")
        function_response = content.parts[0].function_response
        if function_response is None:
            self.fail("Expected function response")
        return function_response

    def test_prune_old_screenshot_parts_prunes_only_turns_beyond_limit(self):
        oldest_turn = self.make_screenshot_turn("navigate", b"oldest")
        middle_turn = self.make_screenshot_turn("navigate", b"middle")
        newest_turn = self.make_screenshot_turn("navigate", b"newest")
        latest_turn = self.make_screenshot_turn("navigate", b"latest")
        contents = [oldest_turn, middle_turn, newest_turn, latest_turn]

        prune_old_screenshot_parts(contents, max_recent_turns_with_screenshots=3)

        self.assertIsNone(self.get_function_response(oldest_turn).parts)
        self.assertIsNotNone(self.get_function_response(middle_turn).parts)
        self.assertIsNotNone(self.get_function_response(newest_turn).parts)
        self.assertIsNotNone(self.get_function_response(latest_turn).parts)

    def test_prune_old_screenshot_parts_ignores_non_predefined_function_responses(self):
        custom_turn = self.make_screenshot_turn(multiply_numbers.__name__, b"custom")
        oldest_turn = self.make_screenshot_turn("navigate", b"oldest")
        middle_turn = self.make_screenshot_turn("navigate", b"middle")
        newest_turn = self.make_screenshot_turn("navigate", b"newest")
        latest_turn = self.make_screenshot_turn("navigate", b"latest")
        contents = [custom_turn, oldest_turn, middle_turn, newest_turn, latest_turn]

        prune_old_screenshot_parts(contents, max_recent_turns_with_screenshots=3)

        self.assertIsNotNone(self.get_function_response(custom_turn).parts)
        self.assertIsNone(self.get_function_response(oldest_turn).parts)
        self.assertIsNotNone(self.get_function_response(middle_turn).parts)
        self.assertIsNotNone(self.get_function_response(newest_turn).parts)
        self.assertIsNotNone(self.get_function_response(latest_turn).parts)


if __name__ == "__main__":
    unittest.main()
