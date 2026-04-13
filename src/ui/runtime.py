import os
from functools import partial
from pathlib import Path

from .session_service import SessionService
from .session_store import SessionStore

ELECTRON_COMMAND_URL_ENV = "COMPUTER_USE_ELECTRON_COMMAND_URL"


def resolve_default_computer_factory():
    electron_command_url = os.getenv(ELECTRON_COMMAND_URL_ENV)
    if not electron_command_url:
        return None

    from computers import ElectronSurfaceComputer

    return partial(ElectronSurfaceComputer, command_url=electron_command_url)


def create_session_store(
    *,
    model_name: str,
    screen_size: tuple[int, int],
    initial_url: str,
    highlight_mouse: bool,
    headless: bool,
    artifacts_root: Path,
) -> SessionStore:
    return SessionStore(
        model_name=model_name,
        screen_size=screen_size,
        initial_url=initial_url,
        highlight_mouse=highlight_mouse,
        headless=headless,
        artifacts_root=artifacts_root,
        computer_factory=resolve_default_computer_factory(),
    )


def create_session_service(
    *,
    model_name: str,
    screen_size: tuple[int, int],
    initial_url: str,
    highlight_mouse: bool,
    headless: bool,
    artifacts_root: Path,
) -> SessionService:
    return SessionService(
        create_session_store(
            model_name=model_name,
            screen_size=screen_size,
            initial_url=initial_url,
            highlight_mouse=highlight_mouse,
            headless=headless,
            artifacts_root=artifacts_root,
        )
    )
