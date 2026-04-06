from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ui.models import CreateSessionResponse, SendMessageRequest, StartSessionRequest
from ui.session_store import SessionStore


def build_sessions_router(store: SessionStore) -> APIRouter:
    router = APIRouter(prefix="/api/sessions", tags=["sessions"])

    def get_session_or_404(session_id: str):
        session = store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return session

    @router.post("", response_model=CreateSessionResponse)
    def create_session() -> CreateSessionResponse:
        session = store.create_session()
        snapshot = session.get_snapshot()
        return CreateSessionResponse(session_id=session.session_id, snapshot=snapshot)

    @router.post("/{session_id}/start")
    def start_session(session_id: str, request: StartSessionRequest):
        session = get_session_or_404(session_id)
        try:
            session.start(request.query)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return session.get_snapshot()

    @router.post("/{session_id}/messages")
    def enqueue_message(session_id: str, request: SendMessageRequest):
        session = get_session_or_404(session_id)
        try:
            session.enqueue_message(request.text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return session.get_snapshot()

    @router.post("/{session_id}/stop")
    def stop_session(session_id: str):
        session = get_session_or_404(session_id)
        session.stop()
        return session.get_snapshot()

    @router.get("/{session_id}")
    def get_snapshot(session_id: str):
        session = get_session_or_404(session_id)
        return session.get_snapshot()

    @router.get("/{session_id}/steps")
    def get_steps(session_id: str, after_step_id: int | None = Query(default=None)):
        session = get_session_or_404(session_id)
        return session.get_steps(after_step_id=after_step_id)

    @router.get("/{session_id}/artifacts/{name}")
    def get_artifact(session_id: str, name: str):
        session = get_session_or_404(session_id)
        try:
            artifact_path = session.get_artifact_path(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc
        return FileResponse(artifact_path)

    return router
