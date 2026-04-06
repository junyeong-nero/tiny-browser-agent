from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import build_sessions_router
from .session_store import SessionStore


DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def create_app(
    *,
    model_name: str,
    screen_size: tuple[int, int],
    initial_url: str,
    highlight_mouse: bool,
    headless: bool,
    artifacts_root: Path,
    allowed_origins: list[str] | None = None,
    store: SessionStore | None = None,
) -> FastAPI:
    session_store = store or SessionStore(
        model_name=model_name,
        screen_size=screen_size,
        initial_url=initial_url,
        highlight_mouse=highlight_mouse,
        headless=headless,
        artifacts_root=artifacts_root,
    )

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or DEFAULT_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(build_sessions_router(session_store))
    return app


def run_ui_server(
    *,
    host: str,
    port: int,
    model_name: str,
    screen_size: tuple[int, int],
    initial_url: str,
    highlight_mouse: bool,
    headless: bool,
    artifacts_root: Path,
    allowed_origins: list[str] | None = None,
) -> None:
    app = create_app(
        model_name=model_name,
        screen_size=screen_size,
        initial_url=initial_url,
        highlight_mouse=highlight_mouse,
        headless=headless,
        artifacts_root=artifacts_root,
        allowed_origins=allowed_origins,
    )
    uvicorn.run(app, host=host, port=port)
