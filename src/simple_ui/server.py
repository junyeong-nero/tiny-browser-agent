"""FastAPI server for the simplified browser-agent control panel."""
import asyncio
import socket
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ui.bridge import (
    register_ws,
    request_task_interrupt,
    reserve_pending_task,
    set_server_loop,
    task_queue,
    unregister_ws,
)
from ui.replay import router as replay_router

_UI_DIR = Path(__file__).parent
_STATIC_DIR = _UI_DIR / "static"
_PANEL_HTML = (_UI_DIR / "panel.html").read_text(encoding="utf-8")
_STATIC_ASSET_NAMES = ("panel.css", "graph.js", "panel.js")

HOST = "127.0.0.1"
_DEFAULT_PORT = 8765
_PORT_RANGE = 20

# Resolved port, set by start() before returning.
port: int = _DEFAULT_PORT


def _find_free_port(start: int, count: int) -> int:
    for p in range(start, start + count):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex((HOST, p)) != 0:
                return p
    raise OSError(f"No free port found in range {start}–{start + count - 1}")


class NoStoreStaticFiles(StaticFiles):
    """Serve simple UI assets without browser caching stale panel code."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def _asset_version(name: str) -> str:
    try:
        return str((_STATIC_DIR / name).stat().st_mtime_ns)
    except OSError:
        return "0"


def _versioned_panel_html() -> str:
    html = _PANEL_HTML
    for name in _STATIC_ASSET_NAMES:
        html = html.replace(
            f'"/static/{name}"',
            f'"/static/{name}?v={_asset_version(name)}"',
        )
    return html


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    set_server_loop(asyncio.get_running_loop())
    yield


app = FastAPI(lifespan=_lifespan)
app.mount("/static", NoStoreStaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(replay_router)


class TaskRequest(BaseModel):
    query: str


@app.get("/")
async def get_panel() -> HTMLResponse:
    return HTMLResponse(_versioned_panel_html(), headers={"Cache-Control": "no-store"})


@app.post("/task")
async def submit_task(body: TaskRequest) -> dict:
    query = body.query.strip()
    if not query:
        return {"ok": False, "error": "Empty query"}
    task_id = reserve_pending_task()
    if task_id is None:
        return {"ok": False, "error": "Task already running"}
    task_queue.put(query)
    return {"ok": True, "task_id": task_id}


@app.post("/interrupt")
async def interrupt_task() -> dict:
    if not request_task_interrupt():
        return {"ok": False, "error": "No active task"}
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    register_ws(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws(ws)


def start(on_ready: threading.Event | None = None) -> None:
    """Run uvicorn. Call in a daemon thread. Sets module-level `port` before signalling ready."""
    global port
    port = _find_free_port(_DEFAULT_PORT, _PORT_RANGE)

    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")

    class _Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            if on_ready is not None:
                on_ready.set()

    asyncio.run(_Server(config).serve())
