import unittest

from google.genai import types
from pydantic import BaseModel

from agents.actor import model_trace


class _Payload(BaseModel):
    value: bytes


class TestModelTrace(unittest.TestCase):
    def test_serialize_content_omits_bytes_and_keeps_tool_payloads(self):
        content = types.Content(
            role="user",
            parts=[
                types.Part(text="hello"),
                types.Part(
                    function_call=types.FunctionCall(
                        name="navigate",
                        args={"url": "https://example.com", "blob": b"secret"},
                    )
                ),
                types.Part(
                    function_response=types.FunctionResponse(
                        name="navigate",
                        response={"payload": _Payload(value=b"secret")},
                    )
                ),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",
                        data=b"\x89PNG",
                    )
                ),
            ],
        )

        serialized = model_trace.serialize_content(content)

        self.assertEqual(serialized["role"], "user")
        self.assertEqual(serialized["parts"][0]["text"], "hello")
        self.assertEqual(serialized["parts"][1]["function_call"]["args"]["blob"], "<bytes omitted>")
        self.assertEqual(
            serialized["parts"][2]["function_response"]["response"],
            {"payload": {"value": "<bytes omitted>"}},
        )
        self.assertEqual(serialized["parts"][3]["inline_data"]["data"], "<bytes omitted>")

    def test_serialize_model_response_keeps_finish_reason_and_content(self):
        response = types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    finish_reason=types.FinishReason.STOP,
                    content=types.Content(role="model", parts=[types.Part(text="done")]),
                )
            ]
        )

        serialized = model_trace.serialize_model_response(response)

        self.assertEqual(serialized["candidates"][0]["finish_reason"], "FinishReason.STOP")
        self.assertEqual(
            serialized["candidates"][0]["content"]["parts"][0]["text"],
            "done",
        )


if __name__ == "__main__":
    unittest.main()
