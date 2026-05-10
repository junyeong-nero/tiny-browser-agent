"""Replay APIs for saved browser-agent log sessions."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

SESSION_ID_RE = re.compile(r"^\d{8}-\d{6}$")
_ALLOWED_HISTORY_EXTS = {".png", ".gif", ".html", ".json", ".yaml"}
_ALLOWED_VIDEO_EXTS = {".webm", ".mp4"}

router = APIRouter()
_logs_history_dir = Path(__file__).resolve().parents[2] / "logs" / "history"


def set_logs_history_dir(path: Path) -> None:
    """Override the logs/history directory, primarily for tests."""
    global _logs_history_dir
    _logs_history_dir = Path(path)


def logs_history_dir() -> Path:
    return _logs_history_dir


def _validate_session_id(session_id: str) -> None:
    if not SESSION_ID_RE.fullmatch(session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")


def _session_dir(session_id: str) -> Path:
    _validate_session_id(session_id)
    base = logs_history_dir().resolve()
    session = (base / session_id).resolve()
    if not _is_relative_to(session, base) or not session.is_dir():
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _step_count(session_dir: Path) -> int:
    history_dir = session_dir / "history"
    if not history_dir.is_dir():
        return 0
    return len(list(history_dir.glob("step-*.json")))


def _has_meaningful_events(session_dir: Path) -> bool:
    return bool(_read_jsonl(session_dir / "events.jsonl"))


def _video_name(session_dir: Path) -> str | None:
    video_dir = session_dir / "video"
    if not video_dir.is_dir():
        return None
    videos = sorted(
        path for path in video_dir.iterdir()
        if path.is_file() and path.suffix in _ALLOWED_VIDEO_EXTS
    )
    if not videos:
        return None
    return f"video/{videos[0].name}"


def _enrich_events_with_session_artifacts(
    events: list[dict[str, Any]],
    session_dir: Path,
) -> list[dict[str, Any]]:
    video_path = _video_name(session_dir)
    if video_path is None:
        return events
    enriched: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "action_executed":
            enriched.append(event)
            continue
        next_event = dict(event)
        artifacts = dict(next_event.get("artifacts") or {})
        artifacts.setdefault("video_path", video_path)
        next_event["artifacts"] = artifacts
        enriched.append(next_event)
    return enriched


def list_sessions() -> list[dict[str, Any]]:
    base = logs_history_dir()
    if not base.is_dir():
        return []
    sessions: list[dict[str, Any]] = []
    for path in sorted(base.iterdir(), reverse=True):
        if not path.is_dir() or not SESSION_ID_RE.fullmatch(path.name):
            continue
        meta = _read_json(path / "session.json")
        step_count = _step_count(path)
        has_events = _has_meaningful_events(path)
        if step_count == 0 and not has_events:
            continue
        sessions.append(
            {
                "id": path.name,
                "started_at": meta.get("started_at") or path.name,
                "query": meta.get("query") or "unknown task",
                "model": meta.get("model_name") or meta.get("model"),
                "step_count": step_count,
                "has_events": has_events,
                "video": _video_name(path),
            }
        )
    return sessions


def load_events(session_id: str) -> list[dict[str, Any]]:
    session_dir = _session_dir(session_id)
    events_path = session_dir / "events.jsonl"
    if events_path.exists():
        events = _read_jsonl(events_path)
        if events:
            return _enrich_events_with_session_artifacts(events, session_dir)
    synthetic_path = session_dir / "events.jsonl.synthetic"
    if synthetic_path.exists():
        events = _read_jsonl(synthetic_path)
        if events:
            return events
    if _step_count(session_dir) == 0:
        return []
    events = synthesize_events(session_dir)
    if events:
        synthetic_path.write_text(
            "".join(json.dumps(event, ensure_ascii=False, default=str) + "\n" for event in events),
            encoding="utf-8",
        )
    return events


def synthesize_events(session_dir: Path) -> list[dict[str, Any]]:
    """Build a minimal replay stream for legacy sessions without events.jsonl."""
    meta = _read_json(session_dir / "session.json")
    actions = _read_jsonl(session_dir / "actions.jsonl")
    step_files = sorted((session_dir / "history").glob("step-*.json"))
    query = meta.get("query") or "unknown task"
    events: list[dict[str, Any]] = [{"type": "task_started", "query": query}]

    for index, step_file in enumerate(step_files):
        step_meta = _read_json(step_file)
        step_id = int(step_meta.get("step") or index + 1)
        action = _action_from_step_or_actions(step_meta, actions, index)
        events.append({"type": "step_started", "step_id": step_id})
        if action:
            events.append(
                {
                    "type": "function_calls_extracted",
                    "step_id": step_id,
                    "function_calls": [action],
                }
            )
        review_event = _review_event_from_step(step_id, step_meta)
        if review_event is not None:
            events.append(review_event)
        action_event: dict[str, Any] = {
            "type": "action_executed",
            "step_id": step_id,
            "artifacts": {
                "step": step_id,
                "screenshot_path": step_meta.get("screenshot_path"),
                "before_screenshot_path": step_meta.get("before_screenshot_path"),
                "after_screenshot_path": step_meta.get("after_screenshot_path") or step_meta.get("screenshot_path"),
                "action_gif_path": step_meta.get("action_gif_path"),
                "action_clip_gif_path": step_meta.get("action_clip_gif_path"),
                "action_capture_frame_count": step_meta.get("action_capture_frame_count"),
                "metadata_path": step_meta.get("metadata_path") or step_file.name,
                "before_metadata_path": step_meta.get("before_metadata_path"),
                "after_metadata_path": step_meta.get("after_metadata_path") or step_meta.get("metadata_path") or step_file.name,
                "a11y_path": step_meta.get("a11y_path"),
                "video_path": _video_name(session_dir),
            },
        }
        if action:
            action_event["action"] = action
        if step_meta.get("url"):
            action_event["env_state"] = {"url": step_meta["url"]}
        events.append(action_event)
        events.append({"type": "step_complete", "step_id": step_id, "status": "complete"})

    events.append({"type": "task_complete", "query": query})
    return events


def _action_from_step_or_actions(
    step_meta: dict[str, Any],
    actions: list[dict[str, Any]],
    index: int,
) -> dict[str, Any] | None:
    raw_action = step_meta.get("action")
    if isinstance(raw_action, dict):
        name = raw_action.get("name") or raw_action.get("tool")
        args = raw_action.get("args") or {}
        if name:
            return {"name": name, "args": args if isinstance(args, dict) else {}}
    if isinstance(raw_action, str) and raw_action:
        return {"name": raw_action, "args": {}}
    if index < len(actions):
        action = actions[index]
        name = action.get("tool") or action.get("name")
        if name:
            args = action.get("args") or {}
            return {"name": name, "args": args if isinstance(args, dict) else {}}
    return None


def _review_event_from_step(step_id: int, step_meta: dict[str, Any]) -> dict[str, Any] | None:
    what = step_meta.get("what") or step_meta.get("action_summary")
    why = step_meta.get("why")
    outcome = step_meta.get("outcome")
    if not any([what, why, outcome]):
        return None
    return {
        "type": "review_metadata_extracted",
        "step_id": step_id,
        "phase_id": step_meta.get("phase_id") or "all-steps",
        "phase_label": step_meta.get("phase_label") or "전체 과정 보기",
        "what": what,
        "why": why,
        "outcome": outcome,
        "action_summary": step_meta.get("action_summary"),
    }


def _artifact_path(session_dir: Path, artifact_path: str) -> Path:
    requested = (session_dir / artifact_path).resolve()
    if not _is_relative_to(requested, session_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    rel = requested.relative_to(session_dir.resolve())
    parts = rel.parts
    allowed = False
    if len(parts) == 2 and parts[0] == "history":
        name = parts[1]
        allowed = name.startswith("step-") and requested.suffix in _ALLOWED_HISTORY_EXTS
    elif len(parts) == 2 and parts[0] == "video":
        allowed = requested.suffix in _ALLOWED_VIDEO_EXTS
    if not allowed:
        raise HTTPException(status_code=404, detail="Artifact not allowed")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return requested


@router.get("/sessions")
async def sessions() -> JSONResponse:
    return JSONResponse({"sessions": list_sessions()}, headers={"Cache-Control": "no-store"})


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str) -> JSONResponse:
    return JSONResponse({"events": load_events(session_id)}, headers={"Cache-Control": "no-store"})


@router.get("/sessions/{session_id}/artifacts/{artifact_path:path}")
async def session_artifact(session_id: str, artifact_path: str) -> FileResponse:
    session_dir = _session_dir(session_id)
    path = _artifact_path(session_dir, artifact_path)
    return FileResponse(path, headers={"Cache-Control": "max-age=3600, immutable"})
