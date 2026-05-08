import json
from pathlib import Path

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


def test_session_id_returns_log_directory_name(tmp_path):
    session_dir = tmp_path / "20260430-123456"
    logger = ArtifactLogger(log_dir=str(session_dir))

    assert logger.session_id() == "20260430-123456"
    assert ArtifactLogger().session_id() is None


def test_log_dir_enables_history_but_not_video_by_default(tmp_path):
    logger = ArtifactLogger(log_dir=str(tmp_path))

    logger.prepare_log_dirs()

    assert logger.history_dir() == tmp_path / "history"
    assert logger.video_dir() is None
    assert (tmp_path / "history").is_dir()
    assert not (tmp_path / "video").exists()


def test_video_dir_is_enabled_separately_from_history(tmp_path):
    logger = ArtifactLogger(
        log_dir=str(tmp_path),
        history_enabled=False,
        video_enabled=True,
    )

    logger.prepare_log_dirs()

    assert logger.history_dir() is None
    assert logger.video_dir() == tmp_path / "video"
    assert not (tmp_path / "history").exists()
    assert (tmp_path / "video").is_dir()


def test_video_only_logger_does_not_write_json_trajectory(tmp_path):
    logger = ArtifactLogger(
        log_dir=str(tmp_path),
        history_enabled=False,
        video_enabled=True,
    )

    logger.record_event({"type": "task_started", "query": "hello"})
    logger.record_action(tool="navigate", args={"url": "https://example.com"})
    logger.record_session_meta({"query": "hello"})

    assert not (tmp_path / "events.jsonl").exists()
    assert not (tmp_path / "actions.jsonl").exists()
    assert not (tmp_path / "session.json").exists()


def test_write_snapshot_creates_action_gif_when_previous_screenshot_exists(tmp_path, monkeypatch):
    logger = ArtifactLogger(log_dir=str(tmp_path))
    monkeypatch.setattr("browser.artifact_logger.shutil.which", lambda name: "/usr/bin/ffmpeg")

    captured_cmd = {}

    def fake_run(cmd, stdout, stderr, check, timeout):
        captured_cmd["cmd"] = cmd
        output_path = cmd[-1]
        Path(output_path).write_bytes(b"GIF89a")

    monkeypatch.setattr("browser.artifact_logger.subprocess.run", fake_run)

    first = logger.write_snapshot(
        screenshot_bytes=b"first",
        url="https://example.com",
        html=None,
        a11y_path=None,
    )
    second = logger.write_snapshot(
        screenshot_bytes=b"second",
        url="https://example.com",
        html=None,
        a11y_path=None,
    )

    assert first["action_gif_path"] is None
    assert second["before_screenshot_path"] == "step-0001.png"
    assert second["after_screenshot_path"] == "step-0002.png"
    assert second["action_gif_path"] == "step-0002.gif"
    filter_complex = captured_cmd["cmd"][captured_cmd["cmd"].index("-filter_complex") + 1]
    assert "palettegen=max_colors=256:stats_mode=diff:reserve_transparent=0" in filter_complex
    assert "paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" in filter_complex
    assert (tmp_path / "history" / "step-0002.gif").read_bytes() == b"GIF89a"
