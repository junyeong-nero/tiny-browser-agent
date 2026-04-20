from pathlib import Path

from .session_service import SessionService
from .session_store import SessionStore


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
        computer_factory=None,
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
