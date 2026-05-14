import unittest

from google.genai import types

from llm.provider.chat_completion_adapter import contents_to_messages, payload_to_response
from tools.types import TOOL_ARGUMENT_ERROR_KEY


class TestChatCompletionAdapter(unittest.TestCase):
    def test_payload_to_response_marks_malformed_tool_arguments(self):
        response = payload_to_response(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "navigate",
                                        "arguments": '{"url": ',
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        )

        candidate = response.candidates[0]
        self.assertIsNotNone(candidate.content)
        assert candidate.content is not None
        function_call = candidate.content.parts[0].function_call
        self.assertIsNotNone(function_call)
        assert function_call is not None
        self.assertEqual(function_call.name, "navigate")
        self.assertIn(TOOL_ARGUMENT_ERROR_KEY, function_call.args)
        error_payload = function_call.args[TOOL_ARGUMENT_ERROR_KEY]
        self.assertEqual(error_payload["error_type"], "JSONDecodeError")
        self.assertIn("Malformed tool arguments JSON", error_payload["error"])

    def test_payload_to_response_preserves_generated_tool_call_id_when_missing(self):
        response = payload_to_response(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "navigate",
                                        "arguments": '{"url": "https://example.com"}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        )

        candidate = response.candidates[0]
        assert candidate.content is not None
        function_call = candidate.content.parts[0].function_call
        assert function_call is not None
        self.assertEqual(function_call.id, "call_0")

        messages = contents_to_messages(
            [
                candidate.content,
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="navigate",
                                id=function_call.id,
                                response={"url": "https://example.com"},
                            )
                        )
                    ],
                ),
            ]
        )
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "call_0")
        self.assertEqual(messages[1]["tool_call_id"], "call_0")

    def test_payload_to_response_empty_choices_has_no_candidates(self):
        response = payload_to_response({"choices": []})

        self.assertEqual(response.candidates, [])


if __name__ == "__main__":
    unittest.main()
