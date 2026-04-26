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
from browser.playwright import PlaywrightBrowser
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
            self.assertEqual(latest_metadata["metadata_path"], "step-0001.json")
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


if __name__ == "__main__":
    unittest.main()
