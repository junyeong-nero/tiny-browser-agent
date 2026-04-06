import uuid
from pathlib import Path
from threading import RLock
from typing import Optional

from .session_controller import AgentFactory, ComputerFactory, SessionController


class SessionStore:
    def __init__(
        self,
        model_name: str,
        screen_size: tuple[int, int],
        initial_url: str,
        highlight_mouse: bool,
        headless: bool,
        artifacts_root: Path,
        computer_factory: Optional[ComputerFactory] = None,
        agent_factory: Optional[AgentFactory] = None,
    ):
        self._model_name = model_name
        self._screen_size = screen_size
        self._initial_url = initial_url
        self._highlight_mouse = highlight_mouse
        self._headless = headless
        self._artifacts_root = artifacts_root
        self._computer_factory = computer_factory
        self._agent_factory = agent_factory
        self._sessions: dict[str, SessionController] = {}
        self._lock = RLock()

    def create_session(self) -> SessionController:
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        kwargs = {}
        if self._computer_factory is not None:
            kwargs["computer_factory"] = self._computer_factory
        if self._agent_factory is not None:
            kwargs["agent_factory"] = self._agent_factory
        controller = SessionController(
            session_id=session_id,
            model_name=self._model_name,
            screen_size=self._screen_size,
            initial_url=self._initial_url,
            highlight_mouse=self._highlight_mouse,
            headless=self._headless,
            artifacts_root=self._artifacts_root,
            **kwargs,
        )
        with self._lock:
            self._sessions[session_id] = controller
        return controller

    def get_session(self, session_id: str) -> SessionController | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
