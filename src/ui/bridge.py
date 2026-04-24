"""Thread-safe bridge: sync agent (main thread) ↔ async WebSocket server (daemon thread)."""
import asyncio
import json
import queue
import threading
from typing import Any

# Task queue: FastAPI thread puts tasks in, BrowserSession pulls them out.
# queue.Queue is thread-safe, so no lock needed for cross-thread access.
task_queue: queue.Queue[str | None] = queue.Queue()

# Active WebSocket connections, guarded by a lock.
_websockets: set = set()
_ws_lock = threading.Lock()

# The event loop running in the uvicorn daemon thread, set on server startup.
_server_loop: asyncio.AbstractEventLoop | None = None

# Last session-level event to replay for late-connecting WebSocket clients.
_last_session_event: dict[str, Any] | None = None


def set_server_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _server_loop
    _server_loop = loop


def register_ws(ws) -> None:
    with _ws_lock:
        _websockets.add(ws)
    if _server_loop and _last_session_event:
        payload = json.dumps(_last_session_event, default=str)
        asyncio.run_coroutine_threadsafe(_send_one(ws, payload), _server_loop)


def unregister_ws(ws) -> None:
    with _ws_lock:
        _websockets.discard(ws)


async def _send_one(ws, payload: str) -> None:
    try:
        await ws.send_text(payload)
    except Exception:
        pass


async def _broadcast(payload: str) -> None:
    with _ws_lock:
        targets = set(_websockets)
    for ws in targets:
        await _send_one(ws, payload)


def _strip_bytes(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return None
    if isinstance(obj, dict):
        return {k: _strip_bytes(v) for k, v in obj.items() if not isinstance(v, bytes)}
    if isinstance(obj, list):
        return [_strip_bytes(v) for v in obj]
    return obj


_SESSION_LEVEL_TYPES = {
    "session_ready",
    "task_started",
    "task_complete",
    "task_failed",
    "session_closed",
}


def emit(event: dict[str, Any]) -> None:
    """Called synchronously from the agent (main) thread. Broadcasts to all WebSocket clients."""
    if _server_loop is None:
        return
    global _last_session_event
    safe_event = _strip_bytes(event)
    if safe_event.get("type") in _SESSION_LEVEL_TYPES:
        _last_session_event = safe_event
    payload = json.dumps(safe_event, default=str)
    asyncio.run_coroutine_threadsafe(_broadcast(payload), _server_loop)
