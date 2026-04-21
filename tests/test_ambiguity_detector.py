import unittest

from agents.post_summary_agent import ActionReviewContext, detect_ambiguity_candidate


class TestAmbiguityDetector(unittest.TestCase):
    def test_flags_typed_text_not_in_query(self):
        candidate = detect_ambiguity_candidate(
            query="search for flights to tokyo",
            current_action=ActionReviewContext(
                action_name="type_text_at",
                action_args={"text": "business class"},
                current_url="https://example.com/search",
            ),
            previous_action=None,
        )

        self.assertIsNotNone(candidate)
        if candidate is None:
            self.fail("Expected typed text ambiguity candidate")
        self.assertEqual(candidate.ambiguity_type, "typed_text_not_in_query")
        self.assertEqual(candidate.review_evidence, ["typed_text_not_in_query"])

    def test_flags_repeated_click_pattern(self):
        candidate = detect_ambiguity_candidate(
            query="open the first result",
            current_action=ActionReviewContext(
                action_name="click_at",
                action_args={"x": 10, "y": 20},
                current_url="https://example.com/results",
            ),
            previous_action=ActionReviewContext(
                action_name="click_at",
                action_args={"x": 10, "y": 20},
                current_url="https://example.com/results",
            ),
        )

        self.assertIsNotNone(candidate)
        if candidate is None:
            self.fail("Expected repeated click ambiguity candidate")
        self.assertEqual(candidate.ambiguity_type, "repeated_click_pattern")

    def test_flags_url_change_without_explicit_navigation(self):
        candidate = detect_ambiguity_candidate(
            query="continue with the current page",
            current_action=ActionReviewContext(
                action_name="click_at",
                action_args={"x": 10, "y": 20},
                current_url="https://example.com/detail",
            ),
            previous_action=ActionReviewContext(
                action_name="click_at",
                action_args={"x": 5, "y": 5},
                current_url="https://example.com/results",
            ),
        )

        self.assertIsNotNone(candidate)
        if candidate is None:
            self.fail("Expected url change ambiguity candidate")
        self.assertEqual(candidate.ambiguity_type, "url_changed_without_navigate")


if __name__ == "__main__":
    unittest.main()
