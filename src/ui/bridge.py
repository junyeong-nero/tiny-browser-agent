"""Thread-safe bridge: sync agent (main thread) ↔ async WebSocket server (daemon thread)."""
import asyncio
import json
import queue
import threading
from collections.abc import Callable
from typing import Any

# Task queue: FastAPI thread puts tasks in, BrowserSession pulls them out.
# queue.Queue is thread-safe, so no lock needed for cross-thread access.
task_queue: queue.Queue[str | None] = queue.Queue()

# Cooperative interrupt flag. The UI server sets it; BrowserSession/BrowserAgent
# poll it between model/tool steps and terminate the current task gracefully.
_interrupt_event = threading.Event()

# Task lifecycle state, guarded by _task_state_lock. A submitted task is first
# reserved as pending, then becomes active when BrowserSession actually starts it.
_task_state_lock = threading.Lock()
_next_task_id = 0
_pending_task_id: int | None = None
_active_task_id: int | None = None

# Active WebSocket connections, guarded by a lock.
_websockets: set = set()
_ws_lock = threading.Lock()

# The event loop running in the uvicorn daemon thread, set on server startup.
_server_loop: asyncio.AbstractEventLoop | None = None

# Last session-level event to replay for late-connecting WebSocket clients.
_last_session_event: dict[str, Any] | None = None

# Event sinks receive the same JSON-safe event stream as WebSocket clients.
_event_sinks: list[Callable[[dict[str, Any]], None]] = []
_event_sinks_lock = threading.Lock()


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


def register_event_sink(fn: Callable[[dict[str, Any]], None]) -> None:
    """Register a synchronous sink for every emitted UI event."""
    with _event_sinks_lock:
        if fn not in _event_sinks:
            _event_sinks.append(fn)


def unregister_event_sink(fn: Callable[[dict[str, Any]], None]) -> None:
    """Remove a previously registered event sink."""
    with _event_sinks_lock:
        try:
            _event_sinks.remove(fn)
        except ValueError:
            pass


def reserve_pending_task() -> int | None:
    """Reserve one UI task slot. Return its id, or None if a task is already pending/running."""
    global _next_task_id, _pending_task_id
    with _task_state_lock:
        if _active_task_id is not None or _pending_task_id is not None:
            return None
        _next_task_id += 1
        _pending_task_id = _next_task_id
        return _pending_task_id


def start_next_task() -> int:
    """Mark the pending task active, clearing stale interrupts only at actual start."""
    global _active_task_id, _pending_task_id, _next_task_id
    with _task_state_lock:
        if _pending_task_id is None:
            _next_task_id += 1
            _active_task_id = _next_task_id
        else:
            _active_task_id = _pending_task_id
            _pending_task_id = None
        task_id = _active_task_id
    _interrupt_event.clear()
    return int(task_id)


def finish_active_task(task_id: int | None = None) -> None:
    """Clear active task state after the session finishes that task."""
    global _active_task_id
    with _task_state_lock:
        if task_id is None or _active_task_id == task_id:
            _active_task_id = None
    _interrupt_event.clear()


def has_active_or_pending_task() -> bool:
    with _task_state_lock:
        return _active_task_id is not None or _pending_task_id is not None


def reset_task_state_for_tests() -> None:
    global _active_task_id, _pending_task_id
    with _task_state_lock:
        _active_task_id = None
        _pending_task_id = None
    _interrupt_event.clear()


def request_task_interrupt() -> bool:
    """Ask the active task to stop at the next cooperative checkpoint.

    For backward-compatible direct endpoint probes with no task present, the
    flag may be set as a stale interrupt; it is cleared only when a real task
    starts. Pending tasks are never interrupted before they become active.
    """
    with _task_state_lock:
        if _active_task_id is None and _pending_task_id is not None:
            return False
    _interrupt_event.set()
    return True


def clear_task_interrupt() -> None:
    """Clear any stale interrupt request before a new task starts."""
    _interrupt_event.clear()


def is_task_interrupted() -> bool:
    """Return whether the active task has been interrupted by the UI."""
    return _interrupt_event.is_set()


def _fan_out_to_sinks(event: dict[str, Any]) -> None:
    with _event_sinks_lock:
        sinks = list(_event_sinks)
    for sink in sinks:
        try:
            sink(dict(event))
        except Exception:
            pass


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
    "task_interrupted",
    "session_closed",
}


def emit(event: dict[str, Any]) -> None:
    """Called synchronously from the agent thread. Broadcast and persist UI events."""
    global _last_session_event
    safe_event = _strip_bytes(event)
    _fan_out_to_sinks(safe_event)
    if _server_loop is None:
        return
    if safe_event.get("type") in _SESSION_LEVEL_TYPES:
        _last_session_event = safe_event
    payload = json.dumps(safe_event, default=str)
    asyncio.run_coroutine_threadsafe(_broadcast(payload), _server_loop)
