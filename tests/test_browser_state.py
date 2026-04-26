import unittest

from browser import BrowserState, EnvState, InteractionState, PageState, ViewportState


class TestBrowserState(unittest.TestCase):
    def test_env_state_keeps_legacy_url_property(self):
        state = EnvState(screenshot=b"png", url="https://example.com")

        self.assertEqual(state.url, "https://example.com")

    def test_env_state_keeps_legacy_screenshot_property(self):
        state = EnvState(screenshot=b"png", url="https://example.com")

        self.assertEqual(state.screenshot, b"png")

    def test_browser_state_exposes_nested_state(self):
        state = BrowserState(
            page=PageState(url="https://example.com", title="Example"),
            viewport=ViewportState(
                screenshot=b"png",
                width=1440,
                height=900,
                scroll_x=10,
                scroll_y=20,
            ),
            interaction=InteractionState(
                focused_element="input[name=q]",
                available_refs=[1, 2, 3],
                last_action="click_at",
            ),
        )

        self.assertEqual(state.page.title, "Example")
        self.assertEqual(state.viewport.width, 1440)
        self.assertEqual(state.viewport.scroll_y, 20)
        self.assertEqual(state.interaction.available_refs, [1, 2, 3])
        self.assertEqual(state.url, "https://example.com")
        self.assertEqual(state.screenshot, b"png")


if __name__ == "__main__":
    unittest.main()
