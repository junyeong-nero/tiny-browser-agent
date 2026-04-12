from pathlib import Path

from .models import CreateSessionResponse, SessionSnapshot, StepRecord, VerificationPayload
from .session_store import SessionStore


class SessionService:
    def __init__(self, store: SessionStore):
        self._store = store

    def create_session(self) -> CreateSessionResponse:
        session = self._store.create_session()
        snapshot = session.get_snapshot()
        return CreateSessionResponse(session_id=session.session_id, snapshot=snapshot)

    def start_session(self, session_id: str, query: str) -> SessionSnapshot:
        session = self._require_session(session_id)
        session.start(query)
        return session.get_snapshot()

    def send_message(self, session_id: str, text: str) -> SessionSnapshot:
        session = self._require_session(session_id)
        session.enqueue_message(text)
        return session.get_snapshot()

    def stop_session(self, session_id: str) -> SessionSnapshot:
        session = self._require_session(session_id)
        session.stop()
        return session.get_snapshot()

    def get_snapshot(self, session_id: str) -> SessionSnapshot:
        session = self._require_session(session_id)
        return session.get_snapshot()

    def get_steps(self, session_id: str, after_step_id: int | None = None) -> list[StepRecord]:
        session = self._require_session(session_id)
        return session.get_steps(after_step_id=after_step_id)

    def get_verification(self, session_id: str) -> VerificationPayload:
        session = self._require_session(session_id)
        return session.get_verification_payload()

    def get_artifact_path(self, session_id: str, name: str) -> Path:
        session = self._require_session(session_id)
        return session.get_artifact_path(name)

    def _require_session(self, session_id: str):
        session = self._store.get_session(session_id)
        if session is None:
            raise LookupError("Session not found.")
        return session
