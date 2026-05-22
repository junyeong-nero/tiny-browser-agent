import unittest

from agents.summarizer.aria_diff import compute_aria_diff


class TestComputeAriaDiff(unittest.TestCase):
    def test_returns_none_when_inputs_missing(self):
        self.assertIsNone(compute_aria_diff(None, None))
        self.assertIsNone(compute_aria_diff("", ""))

    def test_marks_initial_snapshot_when_no_previous(self):
        diff = compute_aria_diff(None, '- button "Search"')
        self.assertIsNotNone(diff)
        assert diff is not None
        self.assertIn("initial", diff.lower())

    def test_no_change_returns_none(self):
        snapshot = '- button "Search"\n- link "Home"\n'
        self.assertIsNone(compute_aria_diff(snapshot, snapshot))

    def test_added_and_removed_lines_are_reported(self):
        prev = '- button "Search"\n- link "Home"\n'
        curr = '- button "Search"\n- link "About"\n- textbox "Query"\n'
        diff = compute_aria_diff(prev, curr)
        assert diff is not None
        self.assertIn('+ - link "About"', diff)
        self.assertIn('+ - textbox "Query"', diff)
        self.assertIn('- - link "Home"', diff)
        self.assertNotIn('button "Search"', diff.split("\n", 1)[1] if "\n" in diff else diff)

    def test_truncates_when_exceeds_max_chars(self):
        prev = ""
        curr = "\n".join(f'- option "item-{i}"' for i in range(500))
        diff = compute_aria_diff(prev, curr, max_chars=400)
        assert diff is not None
        self.assertLessEqual(len(diff), 460)
        self.assertIn("truncated", diff.lower())


if __name__ == "__main__":
    unittest.main()
