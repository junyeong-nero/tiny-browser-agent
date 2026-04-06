import json
import tempfile
import time
import unittest
from contextlib import AbstractContextManager
from pathlib import Path

from fastapi.testclient import TestClient

from ui.server import create_app
from ui.session_controller import SessionController
from ui.session_store import SessionStore


def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for condition.")


class FakeComputer(AbstractContextManager):
    instances = []

    def __init__(
        self,
        screen_size,
        initial_url,
        highlight_mouse,
        headless,
        log_dir,
    ):
        self.screen_size_value = screen_size
        self.initial_url = initial_url
        self.highlight_mouse_value = highlight_mouse
        self.headless = headless
        self.log_dir = Path(log_dir)
        self.history_dir = self.log_dir / "history"
        self.video_dir = self.log_dir / "video"
        self._latest_artifacts = None
        FakeComputer.instances.append(self)

    def __enter__(self):
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        (self.history_dir / "step-0001.png").write_bytes(b"png-bytes")
        (self.history_dir / "step-0001.html").write_text("<html></html>", encoding="utf-8")
        (self.history_dir / "step-0001.json").write_text(
            json.dumps(
                {
                    "step": 1,
                    "timestamp": 123.0,
                    "url": "https://example.com/1",
                    "html_path": "step-0001.html",
                    "screenshot_path": "step-0001.png",
                    "metadata_path": "step-0001.json",
                }
            ),
            encoding="utf-8",
        )
        (self.video_dir / "session.webm").write_bytes(b"webm-bytes")
        self._latest_artifacts = {
            "step": 1,
            "timestamp": 123.0,
            "url": "https://example.com/1",
            "html_path": "step-0001.html",
            "screenshot_path": "step-0001.png",
            "metadata_path": "step-0001.json",
        }
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def latest_artifact_metadata(self):
        return dict(self._latest_artifacts or {})


class FakeAgent:
    instances = []

    def __init__(self, browser_computer, query, model_name, event_sink=None):
        self.browser_computer = browser_computer
        self.query = query
        self.model_name = model_name
        self.event_sink = event_sink
        self.appended_messages = []
        self.final_reasoning = None
        self.run_count = 0
        FakeAgent.instances.append(self)

    def append_user_message(self, text):
        self.appended_messages.append(text)

    def run_one_iteration(self):
        self.run_count += 1
        assert self.event_sink is not None
        if self.run_count == 1:
            self.event_sink({"type": "step_started", "step_id": 1, "timestamp": time.time()})
            self.event_sink(
                {
                    "type": "reasoning_extracted",
                    "step_id": 1,
                    "timestamp": time.time(),
                    "reasoning": "Open the page first.",
                }
            )
            self.event_sink(
                {
                    "type": "function_calls_extracted",
                    "step_id": 1,
                    "timestamp": time.time(),
                    "function_calls": [{"name": "open_web_browser", "args": {}}],
                }
            )
            self.event_sink(
                {
                    "type": "action_executed",
                    "step_id": 1,
                    "timestamp": time.time(),
                    "env_state": {
                        "url": "https://example.com/1",
                        "screenshot": b"png-bytes",
                    },
                    "artifacts": self.browser_computer.latest_artifact_metadata(),
                }
            )
            self.event_sink(
                {
                    "type": "step_complete",
                    "step_id": 1,
                    "timestamp": time.time(),
                    "status": "complete",
                }
            )
            time.sleep(0.05)
            return "CONTINUE"

        self.final_reasoning = "All done."
        self.event_sink({"type": "step_started", "step_id": 2, "timestamp": time.time()})
        self.event_sink(
            {
                "type": "reasoning_extracted",
                "step_id": 2,
                "timestamp": time.time(),
                "reasoning": "Task complete.",
            }
        )
        self.event_sink(
            {
                "type": "function_calls_extracted",
                "step_id": 2,
                "timestamp": time.time(),
                "function_calls": [],
            }
        )
        self.event_sink(
            {
                "type": "step_complete",
                "step_id": 2,
                "timestamp": time.time(),
                "status": "complete",
                "final_reasoning": self.final_reasoning,
            }
        )
        return "COMPLETE"


class BlockingAgent(FakeAgent):
    def run_one_iteration(self):
        self.run_count += 1
        assert self.event_sink is not None
        self.event_sink({"type": "step_started", "step_id": self.run_count, "timestamp": time.time()})
        time.sleep(0.05)
        self.event_sink(
            {
                "type": "step_complete",
                "step_id": self.run_count,
                "timestamp": time.time(),
                "status": "complete",
            }
        )
        return "CONTINUE"


class TestSessionController(unittest.TestCase):
    def setUp(self):
        FakeAgent.instances = []
        FakeComputer.instances = []

    def test_session_controller_updates_snapshot_and_steps(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            controller = SessionController(
                session_id="ses_test",
                model_name="test-model",
                screen_size=(1440, 900),
                initial_url="https://example.com",
                highlight_mouse=False,
                headless=True,
                artifacts_root=Path(tmp_dir),
                computer_factory=FakeComputer,
                agent_factory=FakeAgent,
            )

            controller.start("visit example")
            wait_for(lambda: controller.get_snapshot().status == "complete")

            snapshot = controller.get_snapshot()
            steps = controller.get_steps()

            self.assertEqual(snapshot.current_url, "https://example.com/1")
            self.assertIsNotNone(snapshot.latest_screenshot_b64)
            self.assertEqual(snapshot.latest_step_id, 2)
            self.assertEqual(snapshot.final_reasoning, "All done.")
            self.assertEqual([message.role for message in snapshot.messages], ["user", "assistant"])
            self.assertEqual(len(steps), 2)
            self.assertEqual(steps[0].screenshot_path, "step-0001.png")
            self.assertTrue(controller.get_artifact_path("step-0001.png").exists())

    def test_session_controller_enqueues_messages_for_agent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            controller = SessionController(
                session_id="ses_test",
                model_name="test-model",
                screen_size=(1440, 900),
                initial_url="https://example.com",
                highlight_mouse=False,
                headless=True,
                artifacts_root=Path(tmp_dir),
                computer_factory=FakeComputer,
                agent_factory=FakeAgent,
            )

            controller.start("visit example")
            time.sleep(0.01)
            controller.enqueue_message("follow up")
            wait_for(lambda: controller.get_snapshot().status == "complete")

            self.assertIn("follow up", FakeAgent.instances[-1].appended_messages)

    def test_session_controller_stop_transitions_to_stopped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            controller = SessionController(
                session_id="ses_test",
                model_name="test-model",
                screen_size=(1440, 900),
                initial_url="https://example.com",
                highlight_mouse=False,
                headless=True,
                artifacts_root=Path(tmp_dir),
                computer_factory=FakeComputer,
                agent_factory=BlockingAgent,
            )

            controller.start("visit example")
            time.sleep(0.01)
            controller.stop()
            wait_for(lambda: controller.get_snapshot().status == "stopped")

            self.assertEqual(controller.get_snapshot().status, "stopped")


class TestSessionApi(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = SessionStore(
            model_name="test-model",
            screen_size=(1440, 900),
            initial_url="https://example.com",
            highlight_mouse=False,
            headless=True,
            artifacts_root=Path(self.tmp_dir.name),
            computer_factory=FakeComputer,
            agent_factory=FakeAgent,
        )
        self.app = create_app(
            model_name="test-model",
            screen_size=(1440, 900),
            initial_url="https://example.com",
            highlight_mouse=False,
            headless=True,
            artifacts_root=Path(self.tmp_dir.name),
            store=self.store,
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_health_and_session_endpoints(self):
        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json(), {"status": "ok"})

        create_response = self.client.post("/api/sessions")
        self.assertEqual(create_response.status_code, 200)
        session_id = create_response.json()["session_id"]

        start_response = self.client.post(
            f"/api/sessions/{session_id}/start",
            json={"query": "visit example"},
        )
        self.assertEqual(start_response.status_code, 200)

        wait_for(
            lambda: self.client.get(f"/api/sessions/{session_id}").json()["status"]
            == "complete"
        )

        snapshot_response = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(snapshot_response.status_code, 200)
        self.assertEqual(snapshot_response.json()["final_reasoning"], "All done.")

        steps_response = self.client.get(f"/api/sessions/{session_id}/steps")
        self.assertEqual(steps_response.status_code, 200)
        self.assertEqual(len(steps_response.json()), 2)

        artifact_response = self.client.get(
            f"/api/sessions/{session_id}/artifacts/step-0001.png"
        )
        self.assertEqual(artifact_response.status_code, 200)
        self.assertEqual(artifact_response.content, b"png-bytes")


if __name__ == "__main__":
    unittest.main()
