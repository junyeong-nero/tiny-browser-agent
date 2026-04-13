import json
import tempfile
import time
import unittest
from contextlib import AbstractContextManager
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from google.genai import types
from src.agent import BrowserAgent, multiply_numbers
from src.computers.computer import EnvState
from src.llm.client import LLMClient
from src.ui.models import SessionSnapshot, SessionStatus, StepAction, StepRecord
from src.ui.runtime import resolve_default_computer_factory
from src.ui.session_controller import AgentFactory, SessionController, build_verification_payload
from src.ui.session_service import SessionService
from src.ui.session_store import SessionStore


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
                    "a11y_path": "step-0001.a11y.yaml",
                    "metadata_path": "step-0001.json",
                }
            ),
            encoding="utf-8",
        )
        self._latest_artifacts = {
            "step": 1,
            "timestamp": 123.0,
            "url": "https://example.com/1",
            "html_path": "step-0001.html",
            "screenshot_path": "step-0001.png",
            "a11y_path": "step-0001.a11y.yaml",
            "metadata_path": "step-0001.json",
        }
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def finalize_video_artifact(self):
        (self.video_dir / "session.webm").write_bytes(b"webm-bytes")

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
                    "type": "review_metadata_extracted",
                    "step_id": 1,
                    "timestamp": time.time(),
                    "phase_id": "phase-search",
                    "phase_label": "검색",
                    "phase_summary": "조건에 맞는 결과를 찾는 중입니다.",
                    "user_visible_label": "검색 페이지 열기",
                    "verification_items": [
                        {
                            "id": "verify-seat-class",
                            "message": "좌석 등급을 지정하지 않아 이코노미를 선택했습니다.",
                            "detail": "명시적인 선호가 없어 기본값을 적용했습니다.",
                            "source_step_id": 1,
                            "status": "needs_review",
                            "ambiguity_flag": True,
                            "ambiguity_type": "typed_text_not_in_query",
                            "ambiguity_message": "좌석 등급 입력이 요청에 없었습니다.",
                            "review_evidence": ["typed_text_not_in_query"],
                        }
                    ],
                    "ambiguity_flag": True,
                    "ambiguity_type": "typed_text_not_in_query",
                    "ambiguity_message": "좌석 등급 입력이 요청에 없었습니다.",
                    "review_evidence": ["typed_text_not_in_query"],
                    "a11y_path": "step-0001.a11y.yaml",
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
                "type": "review_metadata_extracted",
                "step_id": 2,
                "timestamp": time.time(),
                "phase_id": "phase-complete",
                "phase_label": "완료",
                "phase_summary": "최종 결과를 정리했습니다.",
                "user_visible_label": "결과 정리",
                "final_result_summary": "요청한 작업을 마쳤고 검토 항목 1개를 남겼습니다.",
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
                agent_factory=cast(AgentFactory, FakeAgent),
            )

            controller.start("visit example")
            wait_for(lambda: controller.get_snapshot().status == "complete")

            snapshot = controller.get_snapshot()
            steps = controller.get_steps()

            self.assertEqual(snapshot.current_url, "https://example.com/1")
            self.assertIsNotNone(snapshot.latest_screenshot_b64)
            self.assertEqual(snapshot.latest_step_id, 2)
            self.assertEqual(snapshot.final_reasoning, "All done.")
            self.assertEqual(snapshot.request_text, "visit example")
            self.assertEqual(
                snapshot.final_result_summary,
                "요청한 작업을 마쳤고 검토 항목 1개를 남겼습니다.",
            )
            self.assertEqual(len(snapshot.verification_items), 1)
            self.assertEqual(snapshot.verification_items[0].source_step_id, 1)
            self.assertEqual(snapshot.verification_items[0].screenshot_path, "step-0001.png")
            self.assertEqual(snapshot.verification_items[0].a11y_path, "step-0001.a11y.yaml")
            self.assertEqual(
                snapshot.verification_items[0].ambiguity_type,
                "typed_text_not_in_query",
            )
            self.assertEqual([message.role for message in snapshot.messages], ["user", "assistant"])
            self.assertEqual(len(steps), 2)
            self.assertEqual(steps[0].screenshot_path, "step-0001.png")
            self.assertEqual(steps[0].a11y_path, "step-0001.a11y.yaml")
            self.assertTrue(steps[0].ambiguity_flag)
            self.assertEqual(steps[0].phase_id, "phase-search")
            self.assertEqual(steps[1].phase_id, "phase-complete")
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
                agent_factory=cast(AgentFactory, FakeAgent),
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
                agent_factory=cast(AgentFactory, BlockingAgent),
            )

            controller.start("visit example")
            time.sleep(0.01)
            controller.stop()
            wait_for(lambda: controller.get_snapshot().status == "stopped")

            self.assertEqual(controller.get_snapshot().status, "stopped")

    def test_session_controller_handles_real_browser_agent_event_payloads(self):
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
                agent_factory=cast(AgentFactory, FakeAgent),
            )
            mock_browser_computer = MagicMock()
            mock_browser_computer.screen_size.return_value = (1000, 1000)
            mock_browser_computer.latest_artifact_metadata.return_value = {
                "screenshot_path": "step-0001.png",
                "html_path": "step-0001.html",
                "metadata_path": "step-0001.json",
            }
            mock_browser_computer.navigate.return_value = EnvState(
                screenshot=b"png-bytes",
                url="https://example.com/real",
            )
            mock_llm_client = MagicMock(spec=LLMClient)
            mock_llm_client.build_function_declaration.return_value = types.FunctionDeclaration(
                name=multiply_numbers.__name__,
                description=multiply_numbers.__doc__,
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "required": ["x", "y"],
                },
            )
            mock_llm_client.generate_content.return_value = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part(text="Navigate first."),
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name="navigate",
                                        args={"url": "https://example.com/real"},
                                    )
                                ),
                            ],
                        )
                    )
                ]
            )
            agent = BrowserAgent(
                browser_computer=mock_browser_computer,
                query="visit example",
                model_name="test-model",
                llm_client=mock_llm_client,
                event_sink=controller._handle_agent_event,
            )

            result = agent.run_one_iteration()

            self.assertEqual(result, "CONTINUE")
            snapshot = controller.get_snapshot()
            steps = controller.get_steps()
            self.assertEqual(snapshot.current_url, "https://example.com/real")
            self.assertIsNotNone(snapshot.latest_screenshot_b64)
            self.assertEqual(snapshot.latest_step_id, 1)
            self.assertEqual(len(snapshot.last_actions), 1)
            self.assertEqual(snapshot.last_actions[0].name, "navigate")
            self.assertEqual(steps[0].screenshot_path, "step-0001.png")
            self.assertEqual(steps[0].html_path, "step-0001.html")
            self.assertEqual(steps[0].metadata_path, "step-0001.json")

    def test_session_controller_builds_grouped_verification_payload(self):
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
                agent_factory=cast(AgentFactory, FakeAgent),
            )

            controller.start("visit example")
            wait_for(lambda: controller.get_snapshot().status == "complete")

            payload = controller.get_verification_payload()

            self.assertEqual(payload.request_text, "visit example")
            self.assertEqual(len(payload.grouped_steps), 2)
            self.assertEqual(payload.grouped_steps[0].id, "phase-search")
            self.assertEqual(payload.grouped_steps[0].step_ids, [1])
            self.assertEqual(payload.grouped_steps[0].a11y_path, "step-0001.a11y.yaml")
            self.assertEqual(payload.grouped_steps[1].id, "phase-complete")


class TestVerificationService(unittest.TestCase):
    def test_build_verification_payload_falls_back_to_url_and_action_grouping(self):
        snapshot = self._build_snapshot()
        payload = build_verification_payload(
            snapshot=snapshot,
            steps=[
                self._build_step(
                    step_id=1,
                    url="https://example.com/search",
                    action_name="click_at",
                    reasoning="Opened the search page.",
                ),
                self._build_step(
                    step_id=2,
                    url="https://example.com/search",
                    action_name="click_at",
                    reasoning="Repeated the search action.",
                ),
                self._build_step(
                    step_id=3,
                    url="https://example.com/results",
                    action_name="type_text_at",
                    reasoning="Typed new filters.",
                ),
            ],
        )

        self.assertEqual(len(payload.grouped_steps), 2)
        self.assertEqual(payload.grouped_steps[0].step_ids, [1, 2])
        self.assertEqual(payload.grouped_steps[0].summary, "Opened the search page. · 2회 반복")
        self.assertEqual(payload.grouped_steps[1].step_ids, [3])
        self.assertEqual(payload.grouped_steps[1].label, "example.com/results")

    def _build_snapshot(self):
        return SessionSnapshot(
            session_id="ses_test",
            status=SessionStatus.COMPLETE,
            current_url="https://example.com/results",
            latest_screenshot_b64=None,
            latest_step_id=3,
            last_reasoning=None,
            last_actions=[],
            messages=[],
            final_reasoning="final reasoning",
            request_text="visit example",
            run_summary="run summary",
            verification_items=[],
            final_result_summary="final summary",
            error_message=None,
            updated_at=1.0,
        )

    def _build_step(self, step_id: int, url: str, action_name: str, reasoning: str):
        return StepRecord(
            step_id=step_id,
            timestamp=float(step_id),
            reasoning=reasoning,
            function_calls=[StepAction(name=action_name, args={})],
            url=url,
            status="complete",
            screenshot_path=f"step-{step_id:04d}.png",
            html_path=f"step-{step_id:04d}.html",
            metadata_path=f"step-{step_id:04d}.json",
            a11y_path=f"step-{step_id:04d}.a11y.yaml",
            error_message=None,
            phase_id=None,
            phase_label=None,
            phase_summary=None,
            user_visible_label=None,
            ambiguity_flag=None,
            ambiguity_type=None,
            ambiguity_message=None,
            review_evidence=[],
        )


class TestUiServerFactoryResolution(unittest.TestCase):
    def test_resolve_default_computer_factory_returns_none_without_env(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(resolve_default_computer_factory())

    def test_resolve_default_computer_factory_uses_electron_surface_when_env_present(self):
        with patch.dict(
            "os.environ",
            {"COMPUTER_USE_ELECTRON_COMMAND_URL": "http://127.0.0.1:4545"},
            clear=True,
        ):
            computer_factory = resolve_default_computer_factory()

        self.assertIsNotNone(computer_factory)


class TestSessionService(unittest.TestCase):
    def setUp(self):
        FakeAgent.instances = []
        FakeComputer.instances = []
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = SessionStore(
            model_name="test-model",
            screen_size=(1440, 900),
            initial_url="https://example.com",
            highlight_mouse=False,
            headless=True,
            artifacts_root=Path(self.tmp_dir.name),
            computer_factory=FakeComputer,
            agent_factory=cast(AgentFactory, FakeAgent),
        )
        self.service = SessionService(self.store)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_service_creates_and_runs_session(self):
        created = self.service.create_session()
        session_id = created.session_id

        start_snapshot = self.service.start_session(session_id, "visit example")
        self.assertEqual(start_snapshot.session_id, session_id)

        wait_for(lambda: self.service.get_snapshot(session_id).status == "complete")

        snapshot = self.service.get_snapshot(session_id)
        steps = self.service.get_steps(session_id)
        verification = self.service.get_verification(session_id)
        artifact_path = self.service.get_artifact_path(session_id, "step-0001.png")

        self.assertEqual(snapshot.final_reasoning, "All done.")
        self.assertEqual(len(steps), 2)
        self.assertEqual(len(verification.grouped_steps), 2)
        self.assertTrue(artifact_path.exists())

    def test_service_raises_lookup_error_for_missing_session(self):
        with self.assertRaises(LookupError):
            self.service.get_snapshot("ses_missing")


if __name__ == "__main__":
    unittest.main()
