import base64
import json
import sys
from pathlib import Path
from typing import Any

from .runtime import create_session_service
from .session_service import SessionService


class DesktopBridgeServer:
    def __init__(self, service: SessionService):
        self._service = service

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if not isinstance(method, str):
            return self._error_response(request_id, "invalid_request", "Method is required.")
        if not isinstance(params, dict):
            return self._error_response(request_id, "invalid_request", "Params must be an object.")

        try:
            result = self._dispatch(method, params)
        except FileNotFoundError as exc:
            return self._error_response(request_id, "not_found", str(exc) or "Artifact not found.")
        except LookupError as exc:
            return self._error_response(request_id, "not_found", str(exc))
        except ValueError as exc:
            return self._error_response(request_id, "invalid_request", str(exc))
        except Exception as exc:  # pragma: no cover - defensive bridge boundary
            return self._error_response(request_id, "internal_error", str(exc))

        return {
            "id": request_id,
            "ok": True,
            "result": _serialize_result(result),
        }

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "healthcheck":
            return {"status": "ok"}
        if method == "createSession":
            return self._service.create_session()
        if method == "startSession":
            return self._service.start_session(_read_string(params, "sessionId"), _read_string(params, "query"))
        if method == "stopSession":
            return self._service.stop_session(_read_string(params, "sessionId"))
        if method == "sendMessage":
            return self._service.send_message(_read_string(params, "sessionId"), _read_string(params, "text"))
        if method == "getSession":
            return self._service.get_snapshot(_read_string(params, "sessionId"))
        if method == "getSteps":
            return self._service.get_steps(
                _read_string(params, "sessionId"),
                after_step_id=_read_optional_int(params, "afterStepId"),
            )
        if method == "getVerification":
            return self._service.get_verification(_read_string(params, "sessionId"))
        if method == "readArtifactText":
            return self._service.read_artifact_text(_read_string(params, "sessionId"), _read_string(params, "name"))
        if method == "readArtifactBinary":
            payload = self._service.read_artifact_bytes(_read_string(params, "sessionId"), _read_string(params, "name"))
            return base64.b64encode(payload).decode("ascii")
        if method == "resolveArtifactPath":
            artifact_path = self._service.get_artifact_path(_read_string(params, "sessionId"), _read_string(params, "name"))
            return str(artifact_path)
        raise ValueError(f"Unsupported bridge method: {method}")

    def _error_response(self, request_id: Any, code: str, message: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        }


def run_desktop_bridge(
    *,
    model_name: str,
    screen_size: tuple[int, int],
    initial_url: str,
    highlight_mouse: bool,
    headless: bool,
    artifacts_root: Path,
) -> None:
    service = create_session_service(
        model_name=model_name,
        screen_size=screen_size,
        initial_url=initial_url,
        highlight_mouse=highlight_mouse,
        headless=headless,
        artifacts_root=artifacts_root,
    )
    server = DesktopBridgeServer(service)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = server.handle_request({"id": None, "method": None, "params": {}})
        else:
            response = server.handle_request(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def _read_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected string field '{key}'.")
    return value


def _read_optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Expected integer field '{key}'.")
    return value


def _serialize_result(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [_serialize_result(item) for item in result]
    if isinstance(result, tuple):
        return [_serialize_result(item) for item in result]
    if isinstance(result, dict):
        return {key: _serialize_result(value) for key, value in result.items()}
    return result
