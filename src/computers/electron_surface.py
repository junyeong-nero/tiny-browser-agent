import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Literal, Optional
from urllib import error, request

from .artifact_logger import ArtifactLogger
from .computer import Computer, EnvState


ELECTRON_COMMAND_URL_ENV = "COMPUTER_USE_ELECTRON_COMMAND_URL"
ELECTRON_FFMPEG_COMMAND_ENV = "COMPUTER_USE_FFMPEG_COMMAND"


class ElectronCommandClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def healthcheck(self) -> None:
        self._request_json("GET", "/health")

    def screen_size(self) -> tuple[int, int]:
        payload = self._request_json("GET", "/computer/screen-size")
        return int(payload["width"]), int(payload["height"])

    def current_state(self) -> dict[str, Any]:
        return self._request_json("POST", "/computer/state")

    def navigate(self, url: str) -> dict[str, Any]:
        return self._request_json("POST", "/computer/navigate", {"url": url})

    def go_back(self) -> dict[str, Any]:
        return self._request_json("POST", "/computer/go-back")

    def go_forward(self) -> dict[str, Any]:
        return self._request_json("POST", "/computer/go-forward")

    def click_at(self, x: int, y: int) -> dict[str, Any]:
        return self._request_json("POST", "/computer/click-at", {"x": x, "y": y})

    def hover_at(self, x: int, y: int) -> dict[str, Any]:
        return self._request_json("POST", "/computer/hover-at", {"x": x, "y": y})

    def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool,
        clear_before_typing: bool,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/computer/type-text-at",
            {
                "x": x,
                "y": y,
                "text": text,
                "pressEnter": press_enter,
                "clearBeforeTyping": clear_before_typing,
            },
        )

    def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> dict[str, Any]:
        return self._request_json("POST", "/computer/scroll-document", {"direction": direction})

    def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/computer/scroll-at",
            {"x": x, "y": y, "direction": direction, "magnitude": magnitude},
        )

    def key_combination(self, keys: list[str]) -> dict[str, Any]:
        return self._request_json("POST", "/computer/key-combination", {"keys": keys})

    def drag_and_drop(
        self,
        x: int,
        y: int,
        destination_x: int,
        destination_y: int,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/computer/drag-and-drop",
            {
                "x": x,
                "y": y,
                "destinationX": destination_x,
                "destinationY": destination_y,
            },
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")

        http_request = request.Request(
            url=f"{self._base_url}{path}",
            data=request_body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(http_request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"Electron command request failed: {detail}") from exc


class ElectronSurfaceComputer(Computer):
    def __init__(
        self,
        screen_size: tuple[int, int],
        initial_url: str = "https://www.google.com",
        search_engine_url: str = "https://www.google.com",
        highlight_mouse: bool = False,
        headless: bool = False,
        log_dir: Optional[str] = None,
        command_url: str | None = None,
        bridge_client: ElectronCommandClient | None = None,
    ):
        del highlight_mouse, headless
        self._screen_size = screen_size
        self._initial_url = initial_url
        self._search_engine_url = search_engine_url
        self._artifact_logger = ArtifactLogger(log_dir=log_dir)

        if bridge_client is not None:
            self._bridge_client = bridge_client
        else:
            resolved_command_url = command_url or os.getenv(ELECTRON_COMMAND_URL_ENV)
            if not resolved_command_url:
                raise ValueError("Electron command URL is required.")
            self._bridge_client = ElectronCommandClient(resolved_command_url)

    def __enter__(self):
        self._prepare_log_dirs()
        self._bridge_client.healthcheck()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def screen_size(self) -> tuple[int, int]:
        width, height = self._bridge_client.screen_size()
        if width > 0 and height > 0:
            return width, height
        return self._screen_size

    def open_web_browser(self) -> EnvState:
        return self.navigate(self._initial_url)

    def click_at(self, x: int, y: int) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.click_at(x, y))

    def hover_at(self, x: int, y: int) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.hover_at(x, y))

    def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool,
        clear_before_typing: bool,
    ) -> EnvState:
        return self._env_state_from_payload(
            self._bridge_client.type_text_at(
                x=x,
                y=y,
                text=text,
                press_enter=press_enter,
                clear_before_typing=clear_before_typing,
            )
        )

    def scroll_document(
        self, direction: Literal["up", "down", "left", "right"]
    ) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.scroll_document(direction))

    def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int,
    ) -> EnvState:
        return self._env_state_from_payload(
            self._bridge_client.scroll_at(x=x, y=y, direction=direction, magnitude=magnitude)
        )

    def wait_5_seconds(self) -> EnvState:
        time.sleep(5)
        return self.current_state()

    def go_back(self) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.go_back())

    def go_forward(self) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.go_forward())

    def search(self) -> EnvState:
        return self.navigate(self._search_engine_url)

    def navigate(self, url: str) -> EnvState:
        normalized_url = url
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url
        return self._env_state_from_payload(self._bridge_client.navigate(normalized_url))

    def key_combination(self, keys: list[str]) -> EnvState:
        return self._env_state_from_payload(self._bridge_client.key_combination(keys))

    def drag_and_drop(
        self, x: int, y: int, destination_x: int, destination_y: int
    ) -> EnvState:
        return self._env_state_from_payload(
            self._bridge_client.drag_and_drop(
                x=x,
                y=y,
                destination_x=destination_x,
                destination_y=destination_y,
            )
        )

    def current_state(self) -> EnvState:
        time.sleep(0.5)
        return self._env_state_from_payload(self._bridge_client.current_state())

    def latest_artifact_metadata(self) -> dict[str, Any] | None:
        return self._artifact_logger.latest_artifact_metadata()

    def history_dir(self) -> Optional[Path]:
        return self._artifact_logger.history_dir()

    def video_dir(self) -> Optional[Path]:
        return self._artifact_logger.video_dir()

    def finalize_video_artifact(self) -> None:
        history_dir = self.history_dir()
        video_dir = self.video_dir()
        if not history_dir or not video_dir:
            return

        session_video_path = video_dir / "session.webm"
        if session_video_path.exists():
            return

        screenshot_pattern = history_dir / "step-%04d.png"
        first_screenshot = history_dir / "step-0001.png"
        if not first_screenshot.exists():
            return

        ffmpeg_command = os.getenv(ELECTRON_FFMPEG_COMMAND_ENV) or shutil.which("ffmpeg")
        if not ffmpeg_command:
            return

        command = [
            ffmpeg_command,
            "-y",
            "-framerate",
            "1",
            "-i",
            str(screenshot_pattern),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuv420p",
            str(session_video_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return

    def _env_state_from_payload(self, payload: dict[str, Any]) -> EnvState:
        screenshot_b64 = payload.get("screenshotBase64")
        url = payload.get("url") or self._initial_url
        if not isinstance(screenshot_b64, str) or not isinstance(url, str):
            raise ValueError("Electron surface payload is missing screenshot/url.")

        screenshot_bytes = base64.b64decode(screenshot_b64)
        if not screenshot_bytes:
            raise ValueError("Electron surface payload contained an empty screenshot.")
        html = payload.get("html")
        if html is not None and not isinstance(html, str):
            html = None
        a11y_text = payload.get("a11yText")
        if a11y_text is not None and not isinstance(a11y_text, str):
            a11y_text = None
        a11y_source = payload.get("a11ySource")
        if not isinstance(a11y_source, str):
            a11y_source = "dom_accessibility_outline"
        a11y_capture_status = payload.get("a11yCaptureStatus")
        if a11y_capture_status not in {"captured", "error", "disabled"}:
            a11y_capture_status = "disabled"
        a11y_capture_error = payload.get("a11yCaptureError")
        if a11y_capture_error is not None and not isinstance(a11y_capture_error, str):
            a11y_capture_error = None

        self._write_history_snapshot(
            screenshot_bytes=screenshot_bytes,
            html=html,
            url=url,
            a11y_text=a11y_text,
            a11y_source=a11y_source,
            a11y_capture_status=a11y_capture_status,
            a11y_capture_error=a11y_capture_error,
        )
        return EnvState(screenshot=screenshot_bytes, url=url)

    def _prepare_log_dirs(self) -> None:
        self._artifact_logger.prepare_log_dirs()

    def _write_history_snapshot(
        self,
        *,
        screenshot_bytes: bytes,
        html: str | None,
        url: str,
        a11y_text: str | None,
        a11y_source: str,
        a11y_capture_status: str,
        a11y_capture_error: str | None,
    ) -> None:
        history_dir = self.history_dir()
        if not history_dir:
            return

        next_step = 1
        latest_metadata = self.latest_artifact_metadata()
        if latest_metadata is not None:
            next_step = int(latest_metadata["step"]) + 1
        step_name = f"step-{next_step:04d}"
        a11y_path = history_dir / f"{step_name}.a11y.yaml"

        persisted_a11y_path = None
        if a11y_text is not None:
            a11y_path.write_text(a11y_text, encoding="utf-8")
            persisted_a11y_path = a11y_path.name

        self._artifact_logger.write_snapshot(
            screenshot_bytes=screenshot_bytes,
            url=url,
            html=html,
            a11y_path=persisted_a11y_path,
            metadata_extra={
                "a11y_source": a11y_source,
                "a11y_capture_status": a11y_capture_status,
                "a11y_capture_error": a11y_capture_error,
            },
        )
