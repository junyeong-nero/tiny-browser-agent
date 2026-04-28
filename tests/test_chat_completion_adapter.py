import unittest

from llm.provider.chat_completion_adapter import payload_to_response
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


if __name__ == "__main__":
    unittest.main()
