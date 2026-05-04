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

from browser.artifact_logger import ArtifactLogger
from browser.playwright import PlaywrightBrowser, playwright
from agents.actor_agent import BrowserAgent


class TestPlaywrightLogging(unittest.TestCase):
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
    def test_agent_enrichment_merges_action_metadata_into_history_json(self, _mock_sleep):
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

            mock_llm_client = MagicMock()
            mock_llm_client.provider_name = "gemini_api"
            mock_llm_client.build_function_declaration.return_value = types.FunctionDeclaration(
                name="multiply_numbers",
                description="Multiplies two numbers.",
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "required": ["x", "y"],
                },
            )

            agent = BrowserAgent(
                browser_computer=computer,
                query="test query",
                model_name="test_model",
                llm_client=mock_llm_client,
                verbose=False,
                step_summarizer=None,
            )

            agent._enrich_persisted_action_metadata(
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
            computer = PlaywrightBrowser(
                screen_size=(1440, 900),
                artifact_logger=ArtifactLogger(log_dir=tmp_dir),
            )
            history_dir = Path(tmp_dir) / "history"
            history_dir.mkdir(parents=True)
            metadata_path = history_dir / "step-0001.json"
            metadata_path.write_text(
                json.dumps({"step": 1, "metadata_path": "step-0001.json"}) + "\n",
                encoding="utf-8",
            )
            computer._artifact_logger._latest_artifact_metadata = {
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

            with patch("browser.playwright.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
                "browser.playwright.subprocess.Popen", side_effect=fake_popen
            ):
                updates = computer._write_action_clip_gif([(10.0, b"frame1"), (12.0, b"frame2")], {"step": 1})
                computer._merge_latest_metadata({"action_clip_gif_path": updates, "action_capture_frame_count": 2})

            self.assertEqual(captured_cmd["cmd"][captured_cmd["cmd"].index("-framerate") + 1], "0.500")
            filter_complex = captured_cmd["cmd"][captured_cmd["cmd"].index("-filter_complex") + 1]
            self.assertIn("palettegen=max_colors=256:stats_mode=diff:reserve_transparent=0", filter_complex)
            self.assertIn("paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", filter_complex)

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["action_clip_gif_path"], "step-0001-action.gif")
            self.assertEqual(metadata["action_capture_frame_count"], 2)
            self.assertEqual(computer.latest_artifact_metadata()["action_clip_gif_path"], "step-0001-action.gif")

    def test_action_gif_samples_sixty_frames_across_full_capture(self):
        computer = PlaywrightBrowser(screen_size=(1440, 900))
        frames = [(float(i), f"frame-{i}".encode()) for i in range(120)]

        sampled = computer._sample_action_frames(frames, max_frames=60)

        self.assertEqual(len(sampled), 60)
        self.assertEqual(sampled[0], frames[0])
        self.assertEqual(sampled[-1], frames[-1])
        self.assertGreater(sampled[1][0], sampled[0][0])


if __name__ == "__main__":
    unittest.main()
