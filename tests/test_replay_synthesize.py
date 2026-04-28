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
