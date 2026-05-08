import unittest

from google.genai import types

from agents.context_compaction import build_effective_contents, summarize_old_contents


class TestContextCompaction(unittest.TestCase):
    def make_initial(self) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text="original task")])

    def make_model_call(self, index: int) -> types.Content:
        return types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name="navigate",
                        args={"url": f"https://example.com/{index}"},
                    )
                )
            ],
        )

    def make_tool_response(
        self,
        index: int,
        *,
        error: str | None = None,
        screenshot: bytes | None = None,
        aria_snapshot: str | None = None,
    ) -> types.Content:
        response = {"url": f"https://example.com/{index}", "result": f"loaded {index}"}
        if error is not None:
            response["error"] = error
        if aria_snapshot is not None:
            response["aria_snapshot"] = aria_snapshot
        parts = None
        if screenshot is not None:
            parts = [
                types.FunctionResponsePart(
                    inline_data=types.FunctionResponseBlob(
                        mime_type="image/png",
                        data=screenshot,
                    )
                )
            ]
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="navigate",
                        response=response,
                        parts=parts,
                    )
                )
            ],
        )

    def test_short_trajectory_returns_original_contents_object(self):
        contents = [
            self.make_initial(),
            types.Content(role="model", parts=[types.Part(text="hi")]),
        ]

        effective = build_effective_contents(
            contents,
            query="original task",
            recent_turn_limit=8,
            compact_after=16,
        )

        self.assertIs(effective, contents)

    def test_summary_excludes_binary_screenshot_bytes_and_keeps_observation_markers(self):
        contents = [
            types.Content(role="model", parts=[types.Part(text="opening page")]),
            self.make_tool_response(
                1,
                error="timeout",
                screenshot=b"secret-image-bytes",
                aria_snapshot="- button: Continue",
            ),
        ]

        summary = summarize_old_contents(contents, query="do task", current_subgoal_id=7)

        self.assertIn("Original user task: do task", summary)
        self.assertIn("Current subgoal: id=7 status=active", summary)
        self.assertIn("Last known URL: https://example.com/1", summary)
        self.assertIn("url=https://example.com/1", summary)
        self.assertIn("error=timeout", summary)
        self.assertIn("result=loaded 1", summary)
        self.assertIn("has_aria=true", summary)
        self.assertIn("has_screenshot=true", summary)
        self.assertNotIn("secret-image-bytes", summary)
        self.assertNotIn("- button: Continue", summary)

    def test_compaction_preserves_function_call_response_pairs_in_recent_contents(self):
        contents = [self.make_initial()]
        for index in range(6):
            contents.extend([self.make_model_call(index), self.make_tool_response(index)])

        effective = build_effective_contents(
            contents,
            query="original task",
            recent_turn_limit=3,
            compact_after=4,
        )

        recent = effective[2:]
        self.assertEqual(len(recent), 4)
        self.assertIsNotNone(recent[0].parts[0].function_call)
        self.assertIsNotNone(recent[1].parts[0].function_response)
        self.assertIsNotNone(recent[2].parts[0].function_call)
        self.assertIsNotNone(recent[3].parts[0].function_response)

    def test_non_positive_recent_limit_uses_summary_only_after_original_task(self):
        contents = [self.make_initial()]
        for index in range(3):
            contents.extend([self.make_model_call(index), self.make_tool_response(index)])

        effective = build_effective_contents(
            contents,
            query="original task",
            recent_turn_limit=0,
            compact_after=1,
        )

        self.assertEqual(len(effective), 2)
        self.assertIs(effective[0], contents[0])
        self.assertTrue(
            effective[1].parts[0].text.startswith("Compacted trajectory summary:")
        )
        self.assertIn(
            "Last known URL: https://example.com/2",
            effective[1].parts[0].text,
        )


if __name__ == "__main__":
    unittest.main()
