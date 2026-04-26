import json
import unittest

from browser import BrowserState, InteractionState, PageState, ViewportState
from browser.state_graph import browser_state_to_graph


class TestStateGraph(unittest.TestCase):
    def make_state(self) -> BrowserState:
        return BrowserState(
            page=PageState(
                url="https://example.com/" + "very-long-path-" * 10,
                title="Example Domain",
                html_path="step-0001.html",
                a11y_path="step-0001.a11y.yaml",
            ),
            viewport=ViewportState(
                screenshot=b"secret-image-bytes",
                width=1440,
                height=900,
                scroll_x=10,
                scroll_y=20,
            ),
            interaction=InteractionState(
                focused_element="input[name=q]",
                available_refs=[1, 2, 3],
            ),
        )

    def test_graph_contains_root_group_and_leaf_nodes(self):
        graph = browser_state_to_graph(self.make_state())
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}

        self.assertEqual(nodes_by_id["browser"]["type"], "root")
        self.assertEqual(nodes_by_id["page"]["label"], "PageState")
        self.assertEqual(nodes_by_id["viewport"]["label"], "ViewportState")
        self.assertEqual(nodes_by_id["interaction"]["label"], "InteractionState")
        self.assertEqual(nodes_by_id["page.url"]["type"], "leaf")
        self.assertEqual(nodes_by_id["viewport.size"]["full_value"], "1440×900")
        self.assertEqual(nodes_by_id["interaction.available_refs"]["full_value"], "3")

    def test_graph_contains_required_links(self):
        graph = browser_state_to_graph(self.make_state())
        links = {(link["source"], link["target"]) for link in graph["links"]}

        self.assertIn(("browser", "page"), links)
        self.assertIn(("browser", "viewport"), links)
        self.assertIn(("browser", "interaction"), links)
        self.assertIn(("page", "page.url"), links)

    def test_graph_excludes_raw_screenshot_bytes(self):
        graph_json = json.dumps(browser_state_to_graph(self.make_state()))

        self.assertNotIn("secret-image-bytes", graph_json)
        self.assertIn("18 bytes", graph_json)

    def test_graph_marks_scoped_changed_fields(self):
        previous = self.make_state()
        current = BrowserState(
            page=PageState(url="https://example.org", title="Changed"),
            viewport=ViewportState(
                screenshot=b"secret-image-bytes",
                width=1440,
                height=900,
                scroll_x=10,
                scroll_y=200,
            ),
            interaction=InteractionState(available_refs=[1]),
        )

        graph = browser_state_to_graph(current, previous)
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}

        self.assertTrue(nodes_by_id["page.url"]["changed"])
        self.assertEqual(nodes_by_id["page.url"]["previous_value"], previous.page.url)
        self.assertEqual(nodes_by_id["page.url"]["current_value"], "https://example.org")
        self.assertTrue(nodes_by_id["page.title"]["changed"])
        self.assertTrue(nodes_by_id["viewport.scroll"]["changed"])
        self.assertTrue(nodes_by_id["interaction.available_refs"]["changed"])
        self.assertNotIn("changed", nodes_by_id["viewport.size"])

    def test_graph_marks_none_boundary_changes(self):
        previous = BrowserState(
            page=PageState(url="https://example.com", title=None),
            viewport=ViewportState(screenshot=b"png", width=100, height=100),
            interaction=InteractionState(focused_element="input[name=q]"),
        )
        current = BrowserState(
            page=PageState(url="https://example.com", title="Loaded"),
            viewport=ViewportState(screenshot=b"png", width=100, height=100),
            interaction=InteractionState(focused_element=None),
        )

        graph = browser_state_to_graph(current, previous)
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}

        self.assertTrue(nodes_by_id["page.title"]["changed"])
        self.assertEqual(nodes_by_id["page.title"]["previous_value"], "")
        self.assertEqual(nodes_by_id["page.title"]["current_value"], "Loaded")
        self.assertTrue(nodes_by_id["interaction.focused_element"]["changed"])
        self.assertEqual(
            nodes_by_id["interaction.focused_element"]["previous_value"],
            "input[name=q]",
        )
        self.assertEqual(nodes_by_id["interaction.focused_element"]["current_value"], "")


if __name__ == "__main__":
    unittest.main()
