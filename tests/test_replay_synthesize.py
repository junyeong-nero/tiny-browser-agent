import json

from ui.replay import synthesize_events


def test_synthesize_events_from_actions_and_step_metadata(tmp_path):
    (tmp_path / "history").mkdir()
    (tmp_path / "session.json").write_text(json.dumps({"query": "find docs"}), encoding="utf-8")
    (tmp_path / "actions.jsonl").write_text(
        json.dumps({"tool": "navigate", "args": {"url": "https://example.com"}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "history" / "step-0001.json").write_text(
        json.dumps(
            {
                "step": 1,
                "url": "https://example.com",
                "what": "Opened Example",
                "why": "Need page content",
                "outcome": "Loaded",
                "screenshot_path": "step-0001.png",
                "metadata_path": "step-0001.json",
            }
        ),
        encoding="utf-8",
    )

    events = synthesize_events(tmp_path)

    assert [event["type"] for event in events] == [
        "task_started",
        "step_started",
        "function_calls_extracted",
        "review_metadata_extracted",
        "action_executed",
        "step_complete",
        "task_complete",
    ]
    assert events[0]["query"] == "find docs"
    assert events[2]["function_calls"] == [{"name": "navigate", "args": {"url": "https://example.com"}}]
    assert events[4]["env_state"] == {"url": "https://example.com"}
    assert events[4]["artifacts"]["screenshot_path"] == "step-0001.png"
    assert events[4]["artifacts"]["after_screenshot_path"] == "step-0001.png"


def test_synthesize_events_includes_before_after_screenshots_and_session_video(tmp_path):
    (tmp_path / "history").mkdir()
    (tmp_path / "video").mkdir()
    (tmp_path / "session.json").write_text(json.dumps({"query": "compare"}), encoding="utf-8")
    (tmp_path / "actions.jsonl").write_text(
        json.dumps({"tool": "click_at", "args": {"x": 1, "y": 2}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "video" / "session_60fps.mp4").write_bytes(b"video")
    (tmp_path / "history" / "step-0002.json").write_text(
        json.dumps(
            {
                "step": 2,
                "url": "https://example.com",
                "screenshot_path": "step-0002.png",
                "before_screenshot_path": "step-0001.png",
                "after_screenshot_path": "step-0002.png",
                "action_gif_path": "step-0002.gif",
                "metadata_path": "step-0002.json",
                "before_metadata_path": "step-0001.json",
                "after_metadata_path": "step-0002.json",
            }
        ),
        encoding="utf-8",
    )

    events = synthesize_events(tmp_path)

    action_event = next(event for event in events if event["type"] == "action_executed")
    artifacts = action_event["artifacts"]
    assert artifacts["before_screenshot_path"] == "step-0001.png"
    assert artifacts["after_screenshot_path"] == "step-0002.png"
    assert artifacts["action_gif_path"] == "step-0002.gif"
    assert artifacts["before_metadata_path"] == "step-0001.json"
    assert artifacts["after_metadata_path"] == "step-0002.json"
    assert artifacts["video_path"] == "video/session_60fps.mp4"
