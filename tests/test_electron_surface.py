import json
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from src.computers.electron_surface import ElectronCommandClient, ElectronSurfaceComputer


class FakeElectronBridgeClient:
    def __init__(self):
        self.calls = []

    def healthcheck(self):
        self.calls.append(("healthcheck", None))

    def screen_size(self):
        self.calls.append(("screen_size", None))
        return (1200, 800)

    def current_state(self):
        self.calls.append(("current_state", None))
        return {
            "a11yCaptureError": None,
            "a11yCaptureStatus": "captured",
            "a11ySource": "dom_accessibility_outline",
            "a11yText": "- body\n  - button: Continue",
            "screenshotBase64": "Zm9v",
            "url": "https://example.com/current",
            "html": "<html>current</html>",
            "width": 1200,
            "height": 800,
        }

    def navigate(self, url: str):
        self.calls.append(("navigate", url))
        return {
            "a11yCaptureError": None,
            "a11yCaptureStatus": "captured",
            "a11ySource": "dom_accessibility_outline",
            "a11yText": "- body\n  - heading: Example",
            "screenshotBase64": "Zm9v",
            "url": url,
            "html": "<html>navigated</html>",
            "width": 1200,
            "height": 800,
        }

    def click_at(self, x: int, y: int):
        self.calls.append(("click_at", (x, y)))
        return {
            "a11yCaptureError": None,
            "a11yCaptureStatus": "captured",
            "a11ySource": "dom_accessibility_outline",
            "a11yText": "- body\n  - link: Clicked",
            "screenshotBase64": "Zm9v",
            "url": "https://example.com/clicked",
            "html": "<html>clicked</html>",
            "width": 1200,
            "height": 800,
        }

    def hover_at(self, x: int, y: int):
        self.calls.append(("hover_at", (x, y)))
        return self.current_state()

    def type_text_at(self, x, y, text, press_enter, clear_before_typing):
        self.calls.append(("type_text_at", (x, y, text, press_enter, clear_before_typing)))
        return self.current_state()

    def scroll_document(self, direction):
        self.calls.append(("scroll_document", direction))
        return self.current_state()

    def scroll_at(self, x, y, direction, magnitude):
        self.calls.append(("scroll_at", (x, y, direction, magnitude)))
        return self.current_state()

    def go_back(self):
        self.calls.append(("go_back", None))
        return self.current_state()

    def go_forward(self):
        self.calls.append(("go_forward", None))
        return self.current_state()

    def key_combination(self, keys):
        self.calls.append(("key_combination", keys))
        return self.current_state()

    def drag_and_drop(self, x, y, destination_x, destination_y):
        self.calls.append(("drag_and_drop", (x, y, destination_x, destination_y)))
        return self.current_state()


class TestElectronSurfaceComputer(unittest.TestCase):
    def test_computer_uses_bridge_client_and_writes_history_artifacts(self):
        bridge_client = FakeElectronBridgeClient()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with ElectronSurfaceComputer(
                screen_size=(1440, 900),
                initial_url="https://example.com/start",
                log_dir=tmp_dir,
                bridge_client=cast(ElectronCommandClient, bridge_client),
            ) as computer:
                opened = computer.open_web_browser()
                clicked = computer.click_at(10, 20)
                current = computer.current_state()

                self.assertEqual(opened.url, "https://example.com/start")
                self.assertEqual(clicked.url, "https://example.com/clicked")
                self.assertEqual(current.url, "https://example.com/current")
                self.assertEqual(computer.screen_size(), (1200, 800))

                history_dir = Path(tmp_dir) / "history"
                video_dir = Path(tmp_dir) / "video"
                self.assertTrue((history_dir / "step-0001.png").exists())
                self.assertTrue((history_dir / "step-0001.html").exists())
                self.assertTrue((history_dir / "step-0001.json").exists())
                self.assertTrue((history_dir / "step-0001.a11y.yaml").exists())
                self.assertTrue(video_dir.exists())
                self.assertIsNotNone(computer.latest_artifact_metadata())

                metadata = json.loads((history_dir / "step-0001.json").read_text())
                self.assertEqual(metadata["a11y_source"], "dom_accessibility_outline")
                self.assertEqual(metadata["a11y_capture_status"], "captured")
                self.assertEqual(metadata["a11y_capture_error"], None)

        self.assertIn(("healthcheck", None), bridge_client.calls)
        self.assertIn(("navigate", "https://example.com/start"), bridge_client.calls)
        self.assertIn(("click_at", (10, 20)), bridge_client.calls)

    @patch("src.computers.electron_surface.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("src.computers.electron_surface.subprocess.run")
    def test_finalize_video_artifact_assembles_session_video(self, mock_run, _mock_which):
        bridge_client = FakeElectronBridgeClient()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with ElectronSurfaceComputer(
                screen_size=(1440, 900),
                initial_url="https://example.com/start",
                log_dir=tmp_dir,
                bridge_client=cast(ElectronCommandClient, bridge_client),
            ) as computer:
                computer.current_state()

                video_dir = Path(tmp_dir) / "video"
                session_video_path = video_dir / "session.webm"

                def create_video(*args, **kwargs):
                    session_video_path.write_bytes(b"webm-bytes")
                    return None

                mock_run.side_effect = create_video

                computer.finalize_video_artifact()

                self.assertTrue(session_video_path.exists())
                self.assertEqual(session_video_path.read_bytes(), b"webm-bytes")
                self.assertTrue(mock_run.called)

    def test_computer_keeps_base_artifacts_when_a11y_is_unavailable(self):
        bridge_client = FakeElectronBridgeClient()
        bridge_client.current_state = lambda: {
            "a11yCaptureError": "snapshot failed",
            "a11yCaptureStatus": "error",
            "a11ySource": "dom_accessibility_outline",
            "a11yText": None,
            "screenshotBase64": "Zm9v",
            "url": "https://example.com/current",
            "html": "<html>current</html>",
            "width": 1200,
            "height": 800,
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            with ElectronSurfaceComputer(
                screen_size=(1440, 900),
                initial_url="https://example.com/start",
                log_dir=tmp_dir,
                bridge_client=cast(ElectronCommandClient, bridge_client),
            ) as computer:
                computer.current_state()

                history_dir = Path(tmp_dir) / "history"
                metadata = json.loads((history_dir / "step-0001.json").read_text())
                self.assertFalse((history_dir / "step-0001.a11y.yaml").exists())
                self.assertEqual(metadata["a11y_path"], None)
                self.assertEqual(metadata["a11y_capture_status"], "error")
                self.assertEqual(metadata["a11y_capture_error"], "snapshot failed")

    @patch("src.computers.electron_surface.time.sleep", return_value=None)
    def test_wait_5_seconds_reuses_current_state(self, _mock_sleep):
        bridge_client = FakeElectronBridgeClient()
        with ElectronSurfaceComputer(
            screen_size=(1440, 900),
            initial_url="https://example.com/start",
            bridge_client=cast(ElectronCommandClient, bridge_client),
        ) as computer:
            state = computer.wait_5_seconds()

        self.assertEqual(state.url, "https://example.com/current")

    def test_empty_screenshot_payload_raises_clear_error(self):
        bridge_client = FakeElectronBridgeClient()
        bridge_client.current_state = lambda: {
            "a11yCaptureError": None,
            "a11yCaptureStatus": "captured",
            "a11ySource": "dom_accessibility_outline",
            "a11yText": "- body\n  - button: Continue",
            "screenshotBase64": "",
            "url": "https://example.com/current",
            "html": "<html>current</html>",
            "width": 1200,
            "height": 800,
        }

        with ElectronSurfaceComputer(
            screen_size=(1440, 900),
            initial_url="https://example.com/start",
            bridge_client=cast(ElectronCommandClient, bridge_client),
        ) as computer:
            with self.assertRaisesRegex(ValueError, "empty screenshot"):
                computer.current_state()
