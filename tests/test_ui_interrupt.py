from unittest.mock import patch

from fastapi.testclient import TestClient

from ui.bridge import clear_task_interrupt, is_task_interrupted, reset_task_state_for_tests, start_next_task
from ui.server import app


def test_interrupt_endpoint_sets_cooperative_interrupt_flag():
    reset_task_state_for_tests()
    clear_task_interrupt()
    client = TestClient(app)

    response = client.post("/interrupt")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert is_task_interrupted() is True
    clear_task_interrupt()
    reset_task_state_for_tests()


def test_task_endpoint_rejects_when_task_is_pending():
    reset_task_state_for_tests()
    client = TestClient(app)
    with patch("ui.server.task_queue") as mock_queue:
        first = client.post("/task", json={"query": "first"})
        second = client.post("/task", json={"query": "second"})

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert second.status_code == 200
    assert second.json() == {"ok": False, "error": "Task already running"}
    mock_queue.put.assert_called_once_with("first")
    reset_task_state_for_tests()


def test_interrupt_does_not_apply_to_pending_task_before_start():
    reset_task_state_for_tests()
    client = TestClient(app)
    with patch("ui.server.task_queue"):
        client.post("/task", json={"query": "pending"})
        response = client.post("/interrupt")

    assert response.json() == {"ok": False, "error": "No active task"}
    assert is_task_interrupted() is False
    start_next_task()
    assert is_task_interrupted() is False
    reset_task_state_for_tests()
