import json

from fastapi.testclient import TestClient

from ui import replay
from ui.server import app


def _make_session(base, session_id="20260428-101500", *, with_events=True):
    session = base / session_id
    (session / "history").mkdir(parents=True)
    (session / "video").mkdir()
    (session / "session.json").write_text(
        json.dumps({"query": "search stuff", "model_name": "model-x", "started_at": "2026-04-28T10:15:00"}),
        encoding="utf-8",
    )
    (session / "history" / "step-0001.json").write_text(json.dumps({"step": 1, "url": "https://example.com"}), encoding="utf-8")
    (session / "history" / "step-0001.png").write_bytes(b"png")
    (session / "video" / "session.webm").write_bytes(b"webm")
    if with_events:
        (session / "events.jsonl").write_text(json.dumps({"type": "task_started", "query": "search stuff"}) + "\n", encoding="utf-8")
    return session


def test_replay_api_lists_sessions_and_serves_events_and_artifacts(tmp_path):
    replay.set_logs_history_dir(tmp_path)
    _make_session(tmp_path)
    client = TestClient(app)

    sessions = client.get("/sessions")
    assert sessions.status_code == 200
    session = sessions.json()["sessions"][0]
    assert session["id"] == "20260428-101500"
    assert session["query"] == "search stuff"
    assert session["model"] == "model-x"
    assert session["step_count"] == 1
    assert session["has_events"] is True
    assert session["video"] == "video/session.webm"

    events = client.get("/sessions/20260428-101500/events")
    assert events.status_code == 200
    assert events.headers["cache-control"] == "no-store"
    assert events.json()["events"] == [{"type": "task_started", "query": "search stuff"}]

    artifact = client.get("/sessions/20260428-101500/artifacts/history/step-0001.png")
    assert artifact.status_code == 200
    assert artifact.content == b"png"
    assert "max-age=3600" in artifact.headers["cache-control"]


def test_replay_api_rejects_bad_ids_and_path_traversal(tmp_path):
    replay.set_logs_history_dir(tmp_path)
    _make_session(tmp_path)
    client = TestClient(app)

    assert client.get("/sessions/bad-id/events").status_code == 400
    assert client.get("/sessions/20260428-101500/artifacts/../session.json").status_code in {400, 404}
    assert client.get("/sessions/20260428-101500/artifacts/session.json").status_code == 404


def test_replay_api_falls_back_to_synthetic_events(tmp_path):
    replay.set_logs_history_dir(tmp_path)
    session = _make_session(tmp_path, with_events=False)
    (session / "actions.jsonl").write_text(json.dumps({"tool": "navigate", "args": {"url": "https://example.com"}}) + "\n", encoding="utf-8")
    client = TestClient(app)

    events = client.get("/sessions/20260428-101500/events").json()["events"]

    assert events[0]["type"] == "task_started"
    assert any(event["type"] == "function_calls_extracted" for event in events)
    assert (session / "events.jsonl.synthetic").exists()
