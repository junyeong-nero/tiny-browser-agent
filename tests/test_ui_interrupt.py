from fastapi.testclient import TestClient

from ui.bridge import clear_task_interrupt, is_task_interrupted
from ui.server import app


def test_interrupt_endpoint_sets_cooperative_interrupt_flag():
    clear_task_interrupt()
    client = TestClient(app)

    response = client.post("/interrupt")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert is_task_interrupted() is True
    clear_task_interrupt()
