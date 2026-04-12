from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..models import CreateSessionResponse, SendMessageRequest, StartSessionRequest
from ..session_service import SessionService


def build_sessions_router(service: SessionService) -> APIRouter:
    router = APIRouter(prefix="/api/sessions", tags=["sessions"])

    @router.post("", response_model=CreateSessionResponse)
    def create_session() -> CreateSessionResponse:
        return service.create_session()

    @router.post("/{session_id}/start")
    def start_session(session_id: str, request: StartSessionRequest):
        try:
            return service.start_session(session_id, request.query)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/{session_id}/messages")
    def enqueue_message(session_id: str, request: SendMessageRequest):
        try:
            return service.send_message(session_id, request.text)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/{session_id}/stop")
    def stop_session(session_id: str):
        try:
            return service.stop_session(session_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/{session_id}")
    def get_snapshot(session_id: str):
        try:
            return service.get_snapshot(session_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/{session_id}/steps")
    def get_steps(session_id: str, after_step_id: int | None = Query(default=None)):
        try:
            return service.get_steps(session_id, after_step_id=after_step_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/{session_id}/verification")
    def get_verification(session_id: str):
        try:
            return service.get_verification(session_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/{session_id}/artifacts/{name}")
    def get_artifact(session_id: str, name: str):
        try:
            artifact_path = service.get_artifact_path(session_id, name)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc
        return FileResponse(artifact_path)

    return router
