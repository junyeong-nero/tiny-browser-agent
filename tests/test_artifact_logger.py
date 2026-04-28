import json

from browser.artifact_logger import ArtifactLogger


def test_record_event_appends_jsonl_without_bytes(tmp_path):
    logger = ArtifactLogger(log_dir=str(tmp_path))

    logger.record_event({"type": "task_started", "query": "hello"})
    logger.record_event({"type": "step_started", "step_id": 1})

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["type"] == "task_started"
    assert first["query"] == "hello"
    assert "ts" in first
    assert second["step_id"] == 1


def test_record_session_meta_writes_once(tmp_path):
    logger = ArtifactLogger(log_dir=str(tmp_path))

    logger.record_session_meta({"query": "first", "model_name": "model-a"})
    logger.record_session_meta({"query": "second", "model_name": "model-b"})

    meta = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert meta == {"query": "first", "model_name": "model-a"}
