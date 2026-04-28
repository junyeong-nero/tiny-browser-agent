from ui.bridge import emit, register_event_sink, unregister_event_sink


def test_emit_calls_registered_sink_with_bytes_removed():
    events = []

    def sink(event):
        events.append(event)

    register_event_sink(sink)
    try:
        emit({"type": "action_executed", "blob": b"bytes", "nested": {"shot": b"png", "ok": True}})
    finally:
        unregister_event_sink(sink)

    assert events == [{"type": "action_executed", "nested": {"ok": True}}]


def test_unregister_event_sink_stops_future_calls():
    events = []

    def sink(event):
        events.append(event)

    register_event_sink(sink)
    unregister_event_sink(sink)

    emit({"type": "task_started", "query": "ignored"})

    assert events == []
