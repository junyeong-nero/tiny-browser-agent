"""Shared FastAPI server plumbing for browser-agent control panels."""
import asyncio
import socket
import threading
from collections.abc import Callable, Sequence
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
    unregister_ws,
)
from ui.replay import router as replay_router

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_RANGE = 20


class TaskRequest(BaseModel):
    query: str


class NoStoreStaticFiles(StaticFiles):
    """Serve UI assets without browser caching stale panel code."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def find_free_port(start: int = DEFAULT_PORT, count: int = PORT_RANGE) -> int:
    for port in range(start, start + count):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise OSError(f"No free port found in range {start}-{start + count - 1}")


def create_panel_app(
    *,
    ui_dir: Path,
    static_asset_names: Sequence[str],
    task_queue_getter: Callable[[], Any],
) -> FastAPI:
    static_dir = ui_dir / "static"
    panel_html = (ui_dir / "panel.html").read_text(encoding="utf-8")

    def asset_version(name: str) -> str:
        try:
            return str((static_dir / name).stat().st_mtime_ns)
        except OSError:
            return "0"

    def versioned_panel_html() -> str:
        html = panel_html
        for name in static_asset_names:
            html = html.replace(
                f'"/static/{name}"',
                f'"/static/{name}?v={asset_version(name)}"',
            )
        return html

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        set_server_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/static", NoStoreStaticFiles(directory=static_dir), name="static")
    app.include_router(replay_router)

    @app.get("/")
    async def get_panel() -> HTMLResponse:
        return HTMLResponse(versioned_panel_html(), headers={"Cache-Control": "no-store"})

    @app.post("/task")
    async def submit_task(body: TaskRequest) -> dict:
        query = body.query.strip()
        if not query:
            return {"ok": False, "error": "Empty query"}
        task_id = reserve_pending_task()
        if task_id is None:
            return {"ok": False, "error": "Task already running"}
        task_queue_getter().put(query)
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

    return app


def run_panel_server(
    app: FastAPI,
    *,
    port: int,
    on_ready: threading.Event | None = None,
) -> None:
    """Run uvicorn for a panel app. Call from a daemon thread."""
    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")

    class _Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            if on_ready is not None:
                on_ready.set()

    asyncio.run(_Server(config).serve())
