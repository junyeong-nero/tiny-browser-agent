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

from computers.playwright.playwright import PlaywrightComputer
from src.agent import BrowserAgent


class TestPlaywrightLogging(unittest.TestCase):
    @patch("computers.playwright.playwright.time.sleep", return_value=None)
    def test_current_state_writes_history_files_when_logging_enabled(self, _mock_sleep):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightComputer(
                screen_size=(1440, 900),
                log_dir=tmp_dir,
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"

            state = computer.current_state()

            history_dir = Path(tmp_dir) / "history"
            self.assertEqual(state.url, "https://example.com")
            self.assertEqual(state.screenshot, b"png-bytes")
            self.assertTrue((history_dir / "step-0001.png").exists())
            self.assertTrue((history_dir / "step-0001.html").exists())
            self.assertTrue((history_dir / "step-0001.json").exists())

            metadata = json.loads((history_dir / "step-0001.json").read_text())
            self.assertEqual(metadata["step"], 1)
            self.assertEqual(metadata["url"], "https://example.com")
            self.assertEqual(metadata["html_path"], "step-0001.html")
            self.assertEqual(metadata["screenshot_path"], "step-0001.png")
            latest_metadata = computer.latest_artifact_metadata()
            self.assertIsNotNone(latest_metadata)
            if latest_metadata is None:
                self.fail("Expected latest artifact metadata")
            self.assertEqual(latest_metadata["step"], 1)
            self.assertEqual(latest_metadata["url"], "https://example.com")
            self.assertEqual(latest_metadata["html_path"], "step-0001.html")
            self.assertEqual(latest_metadata["screenshot_path"], "step-0001.png")
            self.assertEqual(latest_metadata["metadata_path"], "step-0001.json")

    @patch("computers.playwright.playwright.time.sleep", return_value=None)
    def test_agent_enrichment_merges_action_metadata_into_history_json(self, _mock_sleep):
        with tempfile.TemporaryDirectory() as tmp_dir:
            computer = PlaywrightComputer(
                screen_size=(1440, 900),
                log_dir=tmp_dir,
            )
            computer._page = MagicMock()
            computer._page.url = "https://example.com"
            computer._page.screenshot.return_value = b"png-bytes"
            computer._page.content.return_value = "<html>example</html>"
            computer.current_state()

            mock_llm_client = MagicMock()
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


if __name__ == "__main__":
    unittest.main()
