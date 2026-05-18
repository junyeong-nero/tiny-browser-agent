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

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google.genai import types

from agents.summarizer import ActionMetadataWriter, ActionReviewService
from browser.artifact_logger import ArtifactLogger
from browser.playwright import PlaywrightBrowser, playwright
from browser.recording import BrowserRecordingHelper


class TestPlaywrightLogging(unittest.TestCase):
    @patch("browser.playwright.time.sleep", return_value=None)
    def test_highlight_mouse_draws_pointer_marker_when_enabled(self, _mock_sleep):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()

        computer.highlight_mouse(10, 20, kind="click")

        computer._page.evaluate.assert_called_once()
        script, payload = computer._page.evaluate.call_args.args
        self.assertIn("tiny-browser-agent-pointer-highlight", script)
        self.assertIn("data-label", script)
        self.assertIn("9999px rgba(0, 0, 0, .10)", script)
        self.assertIn("2200ms ease-out", script)
        self.assertEqual(payload, {"x": 10, "y": 20, "kind": "click"})
        _mock_sleep.assert_called_once_with(0.28)

    def test_highlight_mouse_is_noop_when_disabled(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=False)
        computer._page = MagicMock()

        computer.highlight_mouse(10, 20, kind="click")

        computer._page.evaluate.assert_not_called()

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_highlight_click_target_draws_actionable_element_at_point(self, _mock_sleep):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()
        computer._page.evaluate.side_effect = [
            {"x": 8.4, "y": 18.6, "width": 101.2, "height": 33.7},
            True,
        ]

        computer.highlight_click_target(10, 20, kind="click")

        element_lookup_script, element_lookup_payload = computer._page.evaluate.call_args_list[
            0
        ].args
        highlight_script, highlight_payload = computer._page.evaluate.call_args_list[1].args
        self.assertIn("elementFromPoint", element_lookup_script)
        self.assertEqual(element_lookup_payload, {"x": 10, "y": 20})
        self.assertIn("tiny-browser-agent-element-highlight", highlight_script)
        self.assertEqual(
            highlight_payload,
            {"x": 8, "y": 19, "width": 101, "height": 34, "kind": "click"},
        )
        _mock_sleep.assert_called_once_with(0.28)

    def test_highlight_click_target_falls_back_to_pointer_marker(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()
        computer._page.evaluate.return_value = None
        computer.highlight_mouse = MagicMock()

        computer.highlight_click_target(10, 20, kind="click")

        computer.highlight_mouse.assert_called_once_with(10, 20, kind="click")

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_highlight_locator_draws_element_box(self, _mock_sleep):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()
        computer._page.evaluate.return_value = True
        locator = MagicMock()
        locator.bounding_box.return_value = {"x": 10, "y": 20, "width": 40, "height": 20}

        computer.highlight_locator(locator, kind="click")

        script, payload = computer._page.evaluate.call_args.args
        self.assertIn("tiny-browser-agent-element-highlight", script)
        self.assertEqual(payload, {"x": 10, "y": 20, "width": 40, "height": 20, "kind": "click"})
        locator.scroll_into_view_if_needed.assert_called_once_with(timeout=1_000)

    def test_click_at_highlights_click_target_before_clicking(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()
        computer.highlight_click_target = MagicMock()
        expected_state = MagicMock()
        computer._state_after_load = MagicMock(return_value=expected_state)

        result = computer.click_at(10, 20)

        computer.highlight_click_target.assert_called_once_with(10, 20, kind="click")
        computer._page.mouse.click.assert_called_once_with(10, 20)
        self.assertEqual(result, expected_state)

    def test_search_uses_duckduckgo_by_default(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        computer.navigate = MagicMock(
            return_value=computer.current_state
        )

        computer.search()

        computer.navigate.assert_called_once_with("https://www.duckduckgo.com")

    def test_search_uses_configured_search_engine_url(self):
        computer = PlaywrightBrowser(
            screen_size=(1440, 900),
            search_engine_url="https://example.com/search",
        )
        computer.navigate = MagicMock(
            return_value=computer.current_state
        )

        computer.search()

        computer.navigate.assert_called_once_with("https://example.com/search")

    @patch("browser.playwright.PlaywrightBrowser._start_frame_stream", return_value=None)
    @patch("browser.playwright.sync_playwright")
    def test_enter_falls_back_to_blank_when_initial_navigation_fails(
        self, mock_sync_playwright, _mock_start_frame_stream
    ):
        page = MagicMock()
        page.goto.side_effect = [
            playwright.sync_api.Error("Page.goto: net::ERR_NAME_NOT_RESOLVED"),
            None,
        ]
        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context
        playwright_instance = MagicMock()
        playwright_instance.chromium.launch.return_value = browser
        mock_sync_playwright.return_value.start.return_value = playwright_instance
        computer = PlaywrightBrowser(
            screen_size=(1440, 900),
            initial_url="https://www.duckduckgo.com/",
        )

        with computer:
            pass

        page.goto.assert_any_call("https://www.duckduckgo.com/")
        page.goto.assert_any_call("about:blank")

    @patch("browser.playwright.PlaywrightBrowser._start_frame_stream", return_value=None)
    @patch("browser.playwright.sync_playwright")
    def test_enter_continues_when_blank_fallback_navigation_is_interrupted(
        self, mock_sync_playwright, _mock_start_frame_stream
    ):
        page = MagicMock()
        page.goto.side_effect = [
            playwright.sync_api.Error("Page.goto: net::ERR_NAME_NOT_RESOLVED"),
            playwright.sync_api.Error(
                'Page.goto: Navigation to "about:blank" is interrupted '
                'by another navigation to "chrome-error://chromewebdata/"'
            ),
        ]
        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context
        playwright_instance = MagicMock()
        playwright_instance.chromium.launch.return_value = browser
        mock_sync_playwright.return_value.start.return_value = playwright_instance
        computer = PlaywrightBrowser(
            screen_size=(1440, 900),
            initial_url="https://www.duckduckgo.com/",
        )

        with computer:
            pass

        page.goto.assert_any_call("https://www.duckduckgo.com/")
        page.goto.assert_any_call("about:blank")

    @patch("browser.playwright.PlaywrightBrowser._start_frame_stream", return_value=None)
    @patch("browser.playwright.sync_playwright")
    def test_headful_enter_can_fit_window_to_screen(
        self, mock_sync_playwright, _mock_start_frame_stream
    ):
        page = MagicMock()
        context = MagicMock()
        context.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = context
        playwright_instance = MagicMock()
        playwright_instance.chromium.launch.return_value = browser
        mock_sync_playwright.return_value.start.return_value = playwright_instance
        computer = PlaywrightBrowser(
            screen_size=(1440, 900),
            headless=False,
            fit_window_to_screen=True,
        )

        with computer:
            pass

        launch_kwargs = playwright_instance.chromium.launch.call_args.kwargs
        self.assertIn("--window-size=1440,900", launch_kwargs["args"])
        self.assertIn("--window-position=0,0", launch_kwargs["args"])
        browser.new_context.assert_called_once_with(no_viewport=True)

    @patch("browser.playwright.PlaywrightBrowser._start_frame_stream", return_value=None)
    @patch("browser.playwright.sync_playwright")
    def test_enter_does_not_record_video_for_log_only_artifacts(
        self,
        mock_sync_playwright,
        _mock_start_frame_stream,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            page = MagicMock()
            context = MagicMock()
            context.new_page.return_value = page
            browser = MagicMock()
            browser.new_context.return_value = context
            playwright_instance = MagicMock()
            playwright_instance.chromium.launch.return_value = browser
            mock_sync_playwright.return_value.start.return_value = playwright_instance
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )

            with computer:
                pass

            context_kwargs = browser.new_context.call_args.kwargs
            self.assertNotIn("record_video_dir", context_kwargs)
            self.assertFalse((Path(tmp_dir) / "video").exists())

    @patch("browser.playwright.PlaywrightBrowser._start_frame_stream", return_value=None)
    @patch("browser.playwright.sync_playwright")
    def test_enter_records_video_when_video_artifacts_are_enabled(
        self,
        mock_sync_playwright,
        _mock_start_frame_stream,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            page = MagicMock()
            context = MagicMock()
            context.new_page.return_value = page
            browser = MagicMock()
            browser.new_context.return_value = context
            playwright_instance = MagicMock()
            playwright_instance.chromium.launch.return_value = browser
            mock_sync_playwright.return_value.start.return_value = playwright_instance
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(
                    log_dir=tmp_dir,
                    history_enabled=False,
                    video_enabled=True,
                ),
            )

            with computer:
                pass

            context_kwargs = browser.new_context.call_args.kwargs
            self.assertEqual(context_kwargs["record_video_dir"], str(Path(tmp_dir) / "video"))
            self.assertEqual(context_kwargs["record_video_size"], {"width": 1440, "height": 900})
            self.assertTrue((Path(tmp_dir) / "video").is_dir())

    def test_handle_new_page_switches_active_page_without_closing_popup(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        current_page = MagicMock()
        new_page = MagicMock()
        new_page.wait_for_load_state = MagicMock()
        computer._page = current_page

        computer._handle_new_page(new_page)

        self.assertIs(computer._page, new_page)
        new_page.wait_for_load_state.assert_called_once_with()
        new_page.close.assert_not_called()

    def test_switch_to_next_tab_cycles_context_pages(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        first_page = MagicMock()
        second_page = MagicMock()
        second_page.url = "https://example.com/second"
        second_page.title.return_value = "Second"
        second_page.viewport_size = {"width": 1440, "height": 900}
        second_page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
        second_page.screenshot.return_value = b"png-bytes"
        second_page.content.return_value = "<html>second</html>"
        second_page.locator.return_value.aria_snapshot.return_value = "- document\n"
        second_page.wait_for_load_state = MagicMock()
        second_page.bring_to_front = MagicMock()

        computer._context = MagicMock()
        computer._context.pages = [first_page, second_page]
        computer._page = first_page

        state = computer.switch_to_next_tab()

        self.assertIs(computer._page, second_page)
        second_page.bring_to_front.assert_called_once_with()
        self.assertEqual(state.url, "https://example.com/second")

    def test_switch_to_previous_tab_cycles_context_pages(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        first_page = MagicMock()
        first_page.url = "https://example.com/first"
        first_page.title.return_value = "First"
        first_page.viewport_size = {"width": 1440, "height": 900}
        first_page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
        first_page.screenshot.return_value = b"png-bytes"
        first_page.content.return_value = "<html>first</html>"
        first_page.locator.return_value.aria_snapshot.return_value = "- document\n"
        first_page.wait_for_load_state = MagicMock()
        first_page.bring_to_front = MagicMock()
        second_page = MagicMock()

        computer._context = MagicMock()
        computer._context.pages = [first_page, second_page]
        computer._page = second_page

        state = computer.switch_to_previous_tab()

        self.assertIs(computer._page, first_page)
        first_page.bring_to_front.assert_called_once_with()
        self.assertEqual(state.url, "https://example.com/first")


    def _make_state_page(self, url: str, title: str):
        page = MagicMock()
        page.url = url
        page.title.return_value = title
        page.viewport_size = {"width": 1440, "height": 900}
        page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
        page.screenshot.return_value = b"png-bytes"
        page.content.return_value = f"<html>{title}</html>"
        page.locator.return_value.aria_snapshot.return_value = "- document\n"
        page.wait_for_load_state = MagicMock()
        page.bring_to_front = MagicMock()
        page.close = MagicMock()
        return page

    def test_list_tabs_returns_active_index_count_url_and_title(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        first_page = self._make_state_page("https://example.com/first", "First")
        second_page = self._make_state_page("https://example.com/second", "Second")
        computer._context = MagicMock()
        computer._context.pages = [first_page, second_page]
        computer._page = second_page

        result = computer.list_tabs()

        self.assertEqual(result["active_tab_index"], 1)
        self.assertEqual(result["tab_count"], 2)
        self.assertEqual(
            result["tabs"],
            [
                {
                    "index": 0,
                    "url": "https://example.com/first",
                    "title": "First",
                    "active": False,
                },
                {
                    "index": 1,
                    "url": "https://example.com/second",
                    "title": "Second",
                    "active": True,
                },
            ],
        )

    def test_switch_to_tab_focuses_index_and_clears_stale_refs(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        first_page = self._make_state_page("https://example.com/first", "First")
        second_page = self._make_state_page("https://example.com/second", "Second")
        computer._context = MagicMock()
        computer._context.pages = [first_page, second_page]
        computer._page = first_page
        computer._aria_ref_map = {1: MagicMock()}
        computer._aria_ref_target_map = {1: first_page}

        state = computer.switch_to_tab(1)

        self.assertIs(computer._page, second_page)
        second_page.bring_to_front.assert_called_once_with()
        self.assertIsNone(computer._aria_ref_map)
        self.assertIsNone(computer._aria_ref_target_map)
        self.assertEqual(state.url, "https://example.com/second")

    def test_switch_to_tab_invalid_index_raises_value_error(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        page = self._make_state_page("https://example.com", "Only")
        computer._context = MagicMock()
        computer._context.pages = [page]
        computer._page = page

        with self.assertRaisesRegex(ValueError, "Invalid tab index 2"):
            computer.switch_to_tab(2)

    def test_close_current_tab_closes_current_and_focuses_previous_tab(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        first_page = self._make_state_page("https://example.com/first", "First")
        second_page = self._make_state_page("https://example.com/second", "Second")
        third_page = self._make_state_page("https://example.com/third", "Third")
        computer._context = MagicMock()
        computer._context.pages = [first_page, second_page, third_page]
        computer._page = third_page
        computer._aria_ref_map = {1: MagicMock()}
        computer._aria_ref_target_map = {1: third_page}

        state = computer.close_current_tab()

        third_page.close.assert_called_once_with()
        self.assertIs(computer._page, second_page)
        second_page.bring_to_front.assert_called_once_with()
        self.assertIsNone(computer._aria_ref_map)
        self.assertIsNone(computer._aria_ref_target_map)
        self.assertEqual(state.url, "https://example.com/second")

    def test_close_current_tab_single_tab_raises_without_closing(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        page = self._make_state_page("https://example.com", "Only")
        computer._context = MagicMock()
        computer._context.pages = [page]
        computer._page = page

        with self.assertRaisesRegex(ValueError, "Cannot close the only open tab"):
            computer.close_current_tab()

        page.close.assert_not_called()

    def test_take_aria_snapshot_merges_multiple_frames_and_resolves_refs_against_frame(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        main_frame = MagicMock()
        main_frame.url = "https://example.com"
        main_frame.locator.return_value.aria_snapshot.return_value = '- button "Search"\n'
        main_frame.get_by_role.return_value.nth.return_value = "main-locator"

        child_frame = MagicMock()
        child_frame.url = "https://accounts.example.com"
        child_frame.locator.return_value.aria_snapshot.return_value = '- textbox "Email"\n'
        child_frame.get_by_role.return_value.nth.return_value = "child-locator"

        computer._page = MagicMock()
        computer._page.url = "https://example.com"
        computer._page.frames = [main_frame, child_frame]

        snapshot = computer.take_aria_snapshot()

        self.assertIn("Frame 1: https://example.com", snapshot.text)
        self.assertIn("Frame 2: https://accounts.example.com", snapshot.text)
        self.assertIn('[1] button "Search"', snapshot.text)
        self.assertIn('[2] textbox "Email"', snapshot.text)
        self.assertEqual(sorted(snapshot.ref_map.keys()), [1, 2])
        self.assertEqual(computer.resolve_ref(2), "child-locator")
        child_frame.get_by_role.assert_called_once_with("textbox", name="Email")

    def test_get_accessibility_tree_reports_frame_aware_snapshot(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        main_frame = MagicMock()
        main_frame.url = "https://example.com"
        main_frame.locator.return_value.aria_snapshot.return_value = '- button "Search"\n'
        main_frame.get_by_role.return_value.nth.return_value = "main-locator"

        child_frame = MagicMock()
        child_frame.url = "https://accounts.example.com"
        child_frame.locator.return_value.aria_snapshot.return_value = '- textbox "Email"\n'
        child_frame.get_by_role.return_value.nth.return_value = "child-locator"

        computer._page = MagicMock()
        computer._page.url = "https://example.com"
        computer._page.frames = [main_frame, child_frame]

        result = computer.get_accessibility_tree()

        self.assertEqual(result["status"], "captured")
        self.assertEqual(result["source"], "frame_locator_aria_snapshot")
        self.assertEqual(result["frame_count"], 2)
        self.assertIn("Frame 2: https://accounts.example.com", result["tree"])
        self.assertEqual(computer.resolve_ref(2), "child-locator")

    def test_take_aria_snapshot_targets_document_body_without_shadow_body_matches(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        page = MagicMock()
        page.url = "https://example.com"
        page.frames = [page]
        page.locator.return_value.aria_snapshot.return_value = '- button "Search"\n'
        computer._page = page

        snapshot = computer.take_aria_snapshot()

        page.locator.assert_called_once_with("html > body")
        self.assertIn('[1] button "Search"', snapshot.text)

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_current_state_writes_history_files_when_logging_enabled(self, _mock_sleep):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.title.return_value = "Example Domain"
            computer._page.viewport_size = {"width": 1440, "height": 900}
            computer._page.evaluate.return_value = {"scrollX": 10, "scrollY": 20}
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"
            computer._page.locator.return_value.aria_snapshot.return_value = "- document\n"
            computer._aria_ref_map = {2: MagicMock(), 1: MagicMock()}
            computer._mark_last_action("navigate")

            state = computer.current_state()

            history_dir = Path(tmp_dir) / "history"
            self.assertEqual(state.url, "https://example.com")
            self.assertEqual(state.screenshot, b"png-bytes")
            self.assertEqual(state.page.title, "Example Domain")
            self.assertEqual(state.page.html_path, "step-0001.html")
            self.assertEqual(state.page.a11y_path, "step-0001.a11y.yaml")
            self.assertEqual(state.viewport.width, 1440)
            self.assertEqual(state.viewport.height, 900)
            self.assertEqual(state.viewport.scroll_x, 10)
            self.assertEqual(state.viewport.scroll_y, 20)
            self.assertEqual(state.interaction.available_refs, [1, 2])
            self.assertEqual(state.interaction.last_action, "navigate")
            self.assertTrue((history_dir / "step-0001.png").exists())
            self.assertTrue((history_dir / "step-0001.html").exists())
            self.assertTrue((history_dir / "step-0001.json").exists())
            self.assertTrue((history_dir / "step-0001.a11y.yaml").exists())

            metadata = json.loads((history_dir / "step-0001.json").read_text())
            self.assertEqual(metadata["step"], 1)
            self.assertEqual(metadata["url"], "https://example.com")
            self.assertEqual(metadata["html_path"], "step-0001.html")
            self.assertEqual(metadata["screenshot_path"], "step-0001.png")
            self.assertIsNone(metadata["before_screenshot_path"])
            self.assertEqual(metadata["after_screenshot_path"], "step-0001.png")
            self.assertIsNone(metadata["action_gif_path"])
            self.assertIsNone(metadata["before_metadata_path"])
            self.assertEqual(metadata["after_metadata_path"], "step-0001.json")
            self.assertEqual(metadata["a11y_path"], "step-0001.a11y.yaml")
            self.assertEqual(metadata["a11y_source"], "body_locator_aria_snapshot")
            self.assertEqual(metadata["a11y_capture_status"], "captured")
            self.assertIn("nodes", metadata["state_graph"])
            self.assertIn("links", metadata["state_graph"])
            self.assertEqual(metadata["state_graph"]["nodes"][0]["id"], "browser")
            nodes_by_id = {node["id"]: node for node in metadata["state_graph"]["nodes"]}
            self.assertEqual(nodes_by_id["interaction.last_action"]["full_value"], "navigate")
            latest_metadata = computer.latest_artifact_metadata()
            self.assertIsNotNone(latest_metadata)
            if latest_metadata is None:
                self.fail("Expected latest artifact metadata")
            self.assertEqual(latest_metadata["step"], 1)
            self.assertEqual(latest_metadata["url"], "https://example.com")
            self.assertEqual(latest_metadata["html_path"], "step-0001.html")
            self.assertEqual(latest_metadata["screenshot_path"], "step-0001.png")
            self.assertIsNone(latest_metadata["before_screenshot_path"])
            self.assertEqual(latest_metadata["after_screenshot_path"], "step-0001.png")
            self.assertIsNone(latest_metadata["action_gif_path"])
            self.assertEqual(latest_metadata["metadata_path"], "step-0001.json")
            self.assertIsNone(latest_metadata["before_metadata_path"])
            self.assertEqual(latest_metadata["after_metadata_path"], "step-0001.json")
            self.assertEqual(latest_metadata["a11y_path"], "step-0001.a11y.yaml")

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_clear_pending_action_prevents_failed_action_from_leaking_to_next_snapshot(
        self,
        _mock_sleep,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.title.return_value = "Example Domain"
            computer._page.viewport_size = {"width": 1440, "height": 900}
            computer._page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"
            computer._page.locator.return_value.aria_snapshot.return_value = "- document\n"

            computer._mark_last_action("click_by_ref")
            computer.clear_pending_action("click_by_ref")
            computer._mark_last_action("open_web_browser")

            state = computer.current_state()

            self.assertEqual(state.interaction.last_action, "open_web_browser")
            metadata = json.loads((Path(tmp_dir) / "history" / "step-0001.json").read_text())
            nodes_by_id = {node["id"]: node for node in metadata["state_graph"]["nodes"]}
            self.assertEqual(
                nodes_by_id["interaction.last_action"]["full_value"],
                "open_web_browser",
            )

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_current_state_keeps_base_artifacts_when_a11y_capture_fails(self, _mock_sleep):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.title.return_value = "Example Domain"
            computer._page.viewport_size = {"width": 1440, "height": 900}
            computer._page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"
            computer._page.locator.return_value.aria_snapshot.side_effect = RuntimeError(
                "aria capture failed"
            )

            computer.current_state()

            history_dir = Path(tmp_dir) / "history"
            self.assertTrue((history_dir / "step-0001.png").exists())
            self.assertTrue((history_dir / "step-0001.html").exists())
            self.assertTrue((history_dir / "step-0001.json").exists())
            self.assertFalse((history_dir / "step-0001.a11y.yaml").exists())

            metadata = json.loads((history_dir / "step-0001.json").read_text())
            self.assertIsNone(metadata["a11y_path"])
            self.assertEqual(metadata["a11y_capture_status"], "error")
            self.assertEqual(metadata["a11y_capture_error"], "aria capture failed")

    @patch("browser.playwright.time.sleep", return_value=None)
    def test_metadata_writer_merges_action_metadata_into_history_json(self, _mock_sleep):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.title.return_value = "Example Domain"
            computer._page.viewport_size = {"width": 1440, "height": 900}
            computer._page.evaluate.return_value = {"scrollX": 0, "scrollY": 0}
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"
            computer._page.locator.return_value.aria_snapshot.return_value = "- document\n"
            computer.current_state()

            writer = ActionMetadataWriter(
                browser_computer=computer,
                review_service=ActionReviewService(query="test query", step_summarizer=None),
            )
            writer.enrich_persisted_action_metadata(
                step_id=1,
                function_call_index=1,
                function_call=types.FunctionCall(
                    name="navigate",
                    args={"url": "https://example.com"},
                ),
                reasoning="Inspect the destination page.",
                artifacts=computer.latest_artifact_metadata(),
                ambiguity_candidate=None,
            )

            metadata = json.loads((Path(tmp_dir) / "history" / "step-0001.json").read_text())
            self.assertEqual(metadata["step"], 1)
            self.assertEqual(metadata["url"], "https://example.com")
            self.assertEqual(metadata["html_path"], "step-0001.html")
            self.assertEqual(metadata["screenshot_path"], "step-0001.png")
            self.assertEqual(metadata["action"], {"name": "navigate", "args": {"url": "https://example.com"}})
            self.assertEqual(metadata["action_summary"], "Navigated to https://example.com")
            self.assertEqual(metadata["reason"], "Inspect the destination page.")
            self.assertEqual(metadata["reasoning_text"], "Inspect the destination page.")
            self.assertEqual(metadata["summary_source"], "app_derived")
            self.assertEqual(metadata["model_step_id"], 1)
            self.assertEqual(metadata["function_call_index_within_step"], 1)
            self.assertFalse(metadata["ambiguity_flag"])
            self.assertEqual(metadata["review_evidence"], [])
            self.assertEqual(metadata["a11y_path"], "step-0001.a11y.yaml")

    def test_action_clip_gif_updates_latest_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_logger = ArtifactLogger(log_dir=tmp_dir)
            fake_shutil = MagicMock()
            fake_shutil.which.return_value = "/usr/bin/ffmpeg"
            fake_subprocess = MagicMock()
            fake_subprocess.PIPE = object()
            fake_subprocess.DEVNULL = object()
            recording = BrowserRecordingHelper(
                artifact_logger=artifact_logger,
                subprocess_module=fake_subprocess,
                shutil_module=fake_shutil,
            )
            history_dir = Path(tmp_dir) / "history"
            history_dir.mkdir(parents=True)
            metadata_path = history_dir / "step-0001.json"
            metadata_path.write_text(
                json.dumps({"step": 1, "metadata_path": "step-0001.json"}) + "\n",
                encoding="utf-8",
            )
            artifact_logger._latest_artifact_metadata = {
                "step": 1,
                "metadata_path": "step-0001.json",
            }

            captured_cmd = {}

            def fake_popen(cmd, stdin, stdout, stderr):
                captured_cmd["cmd"] = cmd

                class FakeProc:
                    def __init__(self):
                        self.stdin = self

                    def write(self, _frame):
                        return None

                    def close(self):
                        Path(cmd[-1]).write_bytes(b"GIF89a")

                    def wait(self, timeout):
                        return 0

                return FakeProc()

            fake_subprocess.Popen.side_effect = fake_popen

            updates = recording.write_action_clip_gif(
                [(10.0, b"frame1"), (12.0, b"frame2")],
                {"step": 1},
            )
            recording.merge_latest_metadata(
                {"action_clip_gif_path": updates, "action_capture_frame_count": 2}
            )

            self.assertEqual(captured_cmd["cmd"][captured_cmd["cmd"].index("-framerate") + 1], "0.500")
            filter_complex = captured_cmd["cmd"][captured_cmd["cmd"].index("-filter_complex") + 1]
            self.assertIn(
                "tpad=start_mode=clone:start_duration=0.35:stop_mode=clone:stop_duration=0.85",
                filter_complex,
            )
            self.assertIn("scale=w='min(iw\\,1920)':h='min(ih\\,1080)'", filter_complex)
            self.assertIn("force_original_aspect_ratio=decrease", filter_complex)
            self.assertIn("force_divisible_by=2", filter_complex)
            self.assertNotIn("scale=640", filter_complex)
            self.assertIn("palettegen=max_colors=256:stats_mode=full:reserve_transparent=0", filter_complex)
            self.assertIn("paletteuse=dither=sierra2_4a", filter_complex)

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["action_clip_gif_path"], "step-0001-action.gif")
            self.assertEqual(metadata["action_capture_frame_count"], 2)
            self.assertEqual(
                artifact_logger.latest_artifact_metadata()["action_clip_gif_path"],
                "step-0001-action.gif",
            )

    def test_action_capture_seeds_previous_observation_frame(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_logger = ArtifactLogger(log_dir=tmp_dir)
            fake_shutil = MagicMock()
            fake_shutil.which.return_value = "/usr/bin/ffmpeg"
            fake_subprocess = MagicMock()
            recording = BrowserRecordingHelper(
                artifact_logger=artifact_logger,
                subprocess_module=fake_subprocess,
                shutil_module=fake_shutil,
            )
            recording.update_frame_buffer(b"before-action")
            cdp_session = MagicMock()
            context = MagicMock()
            context.new_cdp_session.return_value = cdp_session

            recording.begin_action_capture(page=MagicMock(), context=context)

            self.assertIsNotNone(recording._action_capture_frames)
            if recording._action_capture_frames is None:
                self.fail("Expected action capture frames")
            self.assertEqual(recording._action_capture_frames[0][1], b"before-action")
            cdp_session.send.assert_called_with(
                "Page.startScreencast",
                {"format": "png", "quality": 80, "everyNthFrame": 1},
            )

    def test_action_capture_appends_final_observation_frame_before_writing_gif(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_logger = ArtifactLogger(log_dir=tmp_dir)
            fake_shutil = MagicMock()
            fake_shutil.which.return_value = "/usr/bin/ffmpeg"
            fake_subprocess = MagicMock()
            recording = BrowserRecordingHelper(
                artifact_logger=artifact_logger,
                subprocess_module=fake_subprocess,
                shutil_module=fake_shutil,
            )
            history_dir = Path(tmp_dir) / "history"
            history_dir.mkdir(parents=True)
            metadata_path = history_dir / "step-0001.json"
            metadata_path.write_text(
                json.dumps({"step": 1, "metadata_path": "step-0001.json"}) + "\n",
                encoding="utf-8",
            )
            artifact_logger._latest_artifact_metadata = {
                "step": 1,
                "metadata_path": "step-0001.json",
            }
            recording._action_capture_started_at = 10.0
            recording._action_capture_frames = [(10.0, b"before"), (10.5, b"during")]
            recording.update_frame_buffer(b"after")
            recording.write_action_clip_gif = MagicMock(return_value="step-0001-action.gif")

            updates = recording.end_action_capture(persist=True)

            frames_arg = recording.write_action_clip_gif.call_args.args[0]
            self.assertEqual([frame for _ts, frame in frames_arg], [b"before", b"during", b"after"])
            self.assertEqual(updates["action_capture_frame_count"], 3)
            self.assertEqual(updates["action_clip_gif_path"], "step-0001-action.gif")

    def test_action_capture_discard_does_not_mutate_latest_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_logger = ArtifactLogger(log_dir=tmp_dir)
            fake_shutil = MagicMock()
            fake_shutil.which.return_value = "/usr/bin/ffmpeg"
            fake_subprocess = MagicMock()
            fake_subprocess.PIPE = object()
            fake_subprocess.DEVNULL = object()
            recording = BrowserRecordingHelper(
                artifact_logger=artifact_logger,
                subprocess_module=fake_subprocess,
                shutil_module=fake_shutil,
            )
            history_dir = Path(tmp_dir) / "history"
            history_dir.mkdir(parents=True)
            metadata_path = history_dir / "step-0001.json"
            metadata_path.write_text(
                json.dumps({"step": 1, "metadata_path": "step-0001.json"}) + "\n",
                encoding="utf-8",
            )
            artifact_logger._latest_artifact_metadata = {
                "step": 1,
                "metadata_path": "step-0001.json",
            }
            recording._action_capture_started_at = 10.0
            recording._action_capture_frames = [(10.0, b"frame1"), (11.0, b"frame2")]

            updates = recording.end_action_capture(persist=False)

            self.assertIsNone(updates)
            self.assertFalse(fake_subprocess.Popen.called)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata, {"step": 1, "metadata_path": "step-0001.json"})
            self.assertEqual(
                artifact_logger.latest_artifact_metadata(),
                {"step": 1, "metadata_path": "step-0001.json"},
            )

    def test_action_gif_samples_sixty_frames_across_full_capture(self):
        frames = [(float(i), f"frame-{i}".encode()) for i in range(120)]

        sampled = BrowserRecordingHelper.sample_action_frames(frames, max_frames=60)

        self.assertEqual(len(sampled), 60)
        self.assertEqual(sampled[0], frames[0])
        self.assertEqual(sampled[-1], frames[-1])
        self.assertGreater(sampled[1][0], sampled[0][0])


if __name__ == "__main__":
    unittest.main()
