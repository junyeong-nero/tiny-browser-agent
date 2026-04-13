import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.ui.desktop_bridge import DesktopBridgeServer
from src.ui.models import SessionSnapshot, SessionStatus


class TestDesktopBridgeServer(unittest.TestCase):
    def test_handle_request_serializes_model_results(self):
        service = MagicMock()
        service.create_session.return_value = {
            "session_id": "ses_test",
            "snapshot": SessionSnapshot(
                session_id="ses_test",
                status=SessionStatus.IDLE,
                current_url=None,
                latest_screenshot_b64=None,
                latest_step_id=None,
                last_reasoning=None,
                last_actions=[],
                messages=[],
                final_reasoning=None,
                request_text=None,
                run_summary=None,
                verification_items=[],
                final_result_summary=None,
                error_message=None,
                updated_at=1.0,
            ),
        }
        server = DesktopBridgeServer(service)

        response = server.handle_request({"id": "1", "method": "createSession", "params": {}})

        self.assertEqual(response["id"], "1")
        self.assertEqual(response["ok"], True)
        self.assertEqual(response["result"]["session_id"], "ses_test")
        self.assertEqual(response["result"]["snapshot"]["status"], "idle")

    def test_handle_request_supports_artifact_reads(self):
        service = MagicMock()
        service.read_artifact_bytes.return_value = b"AB"
        service.read_artifact_text.return_value = "hello"
        service.get_artifact_path.return_value = Path("/tmp/example.html")
        server = DesktopBridgeServer(service)

        text_response = server.handle_request(
            {
                "id": "2",
                "method": "readArtifactText",
                "params": {"sessionId": "ses_test", "name": "step-0001.html"},
            }
        )
        binary_response = server.handle_request(
            {
                "id": "3",
                "method": "readArtifactBinary",
                "params": {"sessionId": "ses_test", "name": "step-0001.png"},
            }
        )
        path_response = server.handle_request(
            {
                "id": "4",
                "method": "resolveArtifactPath",
                "params": {"sessionId": "ses_test", "name": "step-0001.html"},
            }
        )

        self.assertEqual(text_response["result"], "hello")
        self.assertEqual(binary_response["result"], "QUI=")
        self.assertEqual(path_response["result"], "/tmp/example.html")

    def test_handle_request_returns_error_for_invalid_payload(self):
        server = DesktopBridgeServer(MagicMock())

        response = server.handle_request({"id": "bad", "method": None, "params": {}})

        self.assertEqual(response["ok"], False)
        self.assertEqual(response["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
