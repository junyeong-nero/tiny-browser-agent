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

from computers.playwright.playwright import PlaywrightComputer


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


if __name__ == "__main__":
    unittest.main()
