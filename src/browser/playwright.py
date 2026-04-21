import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional, cast

import pydantic
import termcolor
import playwright.sync_api
from playwright.sync_api import sync_playwright

from .artifact_logger import ArtifactLogger

FRAME_CAPTURE_FPS = 60


class EnvState(pydantic.BaseModel):
    screenshot: bytes
    url: str


PLAYWRIGHT_INSTALL_HINT = (
    "Playwright browser binaries are missing. Run "
    "`uv run playwright install chromium` and retry."
)

PLAYWRIGHT_KEY_MAP = {
    "backspace": "Backspace",
    "tab": "Tab",
    "return": "Enter",
    "enter": "Enter",
    "shift": "Shift",
    "control": "ControlOrMeta",
    "alt": "Alt",
    "escape": "Escape",
    "space": "Space",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "end": "End",
    "home": "Home",
    "left": "ArrowLeft",
    "up": "ArrowUp",
    "right": "ArrowRight",
    "down": "ArrowDown",
    "insert": "Insert",
    "delete": "Delete",
    "semicolon": ";",
    "equals": "=",
    "multiply": "Multiply",
    "add": "Add",
    "separator": "Separator",
    "subtract": "Subtract",
    "decimal": "Decimal",
    "divide": "Divide",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
    "command": "Meta",
}


class PlaywrightBrowser:
    """Controls a local Chromium browser via Playwright."""

    def __init__(
        self,
        screen_size: tuple[int, int],
        initial_url: str = "https://www.google.com",
        search_engine_url: str = "https://www.google.com",
        highlight_mouse: bool = False,
        headless: bool = False,
        log_dir: Optional[str] = None,
    ):
        self._initial_url = initial_url
        self._screen_size = screen_size
        self._search_engine_url = search_engine_url
        self._highlight_mouse = highlight_mouse
        self._headless = headless
        self._artifact_logger = ArtifactLogger(log_dir=log_dir)
        self._frame_buffer: bytes | None = None
        self._frame_lock = threading.Lock()
        self._frame_thread: Optional[threading.Thread] = None
        self._frame_stop = threading.Event()
        self._ffmpeg_proc: Optional[subprocess.Popen] = None

    def _handle_new_page(self, new_page: playwright.sync_api.Page):
        new_url = new_page.url
        new_page.close()
        self._page.goto(new_url)

    def __enter__(self):
        print("Creating session...")
        self._prepare_log_dirs()
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                args=[
                    "--disable-extensions",
                    "--disable-file-system",
                    "--disable-plugins",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                ],
                headless=self._headless,
            )
        except playwright.sync_api.Error as exc:
            self._playwright.stop()
            if "Executable doesn't exist" in str(exc):
                raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc
            raise
        viewport_size = cast(
            playwright.sync_api.ViewportSize,
            {
                "width": self._screen_size[0],
                "height": self._screen_size[1],
            },
        )
        context_kwargs: dict[str, Any] = {"viewport": viewport_size}
        video_dir = self.video_dir()
        if video_dir:
            context_kwargs["record_video_dir"] = str(video_dir)
            context_kwargs["record_video_size"] = viewport_size
        self._context = self._browser.new_context(**context_kwargs)
        self._page = self._context.new_page()
        self._page.goto(self._initial_url)
        self._context.on("page", self._handle_new_page)
        termcolor.cprint("Started local playwright.", color="green", attrs=["bold"])
        history_dir = self.history_dir()
        if history_dir:
            print(f"Logging Playwright history to {history_dir.parent}")
        self._start_frame_stream()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_frame_stream()
        if self._context:
            self._context.close()
        try:
            self._browser.close()
        except Exception as e:
            if "Browser.close: Connection closed while reading from the driver" not in str(e):
                raise
        self._playwright.stop()

    def open_web_browser(self) -> EnvState:
        return self.current_state()

    def click_at(self, x: int, y: int) -> EnvState:
        self.highlight_mouse(x, y)
        self._page.mouse.click(x, y)
        self._page.wait_for_load_state()
        return self.current_state()

    def hover_at(self, x: int, y: int) -> EnvState:
        self.highlight_mouse(x, y)
        self._page.mouse.move(x, y)
        self._page.wait_for_load_state()
        return self.current_state()

    def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool = False,
        clear_before_typing: bool = True,
    ) -> EnvState:
        self.highlight_mouse(x, y)
        self._page.mouse.click(x, y)
        self._page.wait_for_load_state()

        if clear_before_typing:
            if sys.platform == "darwin":
                self.key_combination(["Command", "A"])
            else:
                self.key_combination(["Control", "A"])
            self.key_combination(["Delete"])

        self._page.keyboard.type(text)
        self._page.wait_for_load_state()

        if press_enter:
            self.key_combination(["Enter"])
        self._page.wait_for_load_state()
        return self.current_state()

    def _horizontal_document_scroll(self, direction: Literal["left", "right"]) -> EnvState:
        horizontal_scroll_amount = self.screen_size()[0] // 2
        sign = "" if direction == "right" else "-"
        self._page.evaluate(f"window.scrollBy({sign}{horizontal_scroll_amount}, 0); ")
        self._page.wait_for_load_state()
        return self.current_state()

    def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> EnvState:
        if direction == "down":
            return self.key_combination(["PageDown"])
        elif direction == "up":
            return self.key_combination(["PageUp"])
        elif direction in ("left", "right"):
            return self._horizontal_document_scroll(direction)
        else:
            raise ValueError("Unsupported direction: ", direction)

    def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int = 800,
    ) -> EnvState:
        self.highlight_mouse(x, y)
        self._page.mouse.move(x, y)
        self._page.wait_for_load_state()

        dx = 0
        dy = 0
        if direction == "up":
            dy = -magnitude
        elif direction == "down":
            dy = magnitude
        elif direction == "left":
            dx = -magnitude
        elif direction == "right":
            dx = magnitude
        else:
            raise ValueError("Unsupported direction: ", direction)

        self._page.mouse.wheel(dx, dy)
        self._page.wait_for_load_state()
        return self.current_state()

    def wait_5_seconds(self) -> EnvState:
        time.sleep(5)
        return self.current_state()

    def go_back(self) -> EnvState:
        self._page.go_back()
        self._page.wait_for_load_state()
        return self.current_state()

    def go_forward(self) -> EnvState:
        self._page.go_forward()
        self._page.wait_for_load_state()
        return self.current_state()

    def search(self) -> EnvState:
        return self.navigate(self._search_engine_url)

    def navigate(self, url: str) -> EnvState:
        normalized_url = url if url.startswith(("http://", "https://")) else "https://" + url
        self._page.goto(normalized_url)
        self._page.wait_for_load_state()
        return self.current_state()

    def reload_page(self) -> EnvState:
        self._page.reload()
        self._page.wait_for_load_state()
        return self.current_state()

    def upload_file(self, x: int, y: int, path: str) -> EnvState:
        resolved_path = Path(path)
        if not resolved_path.is_absolute():
            raise ValueError(f"upload_file requires an absolute path; got: {path}")
        if not resolved_path.exists():
            raise FileNotFoundError(f"upload_file target does not exist: {path}")

        with self._page.expect_file_chooser() as file_chooser_info:
            self._page.mouse.click(x, y)
        file_chooser_info.value.set_files(str(resolved_path))
        return self.current_state()

    def get_accessibility_tree(self) -> dict[str, Any]:
        source = "body_locator_aria_snapshot"
        url = self._page.url
        try:
            tree = self._page.locator("body").aria_snapshot()
        except Exception as exc:
            return {
                "tree": None,
                "url": url,
                "source": source,
                "status": "error",
                "error": str(exc),
            }
        return {
            "tree": tree,
            "url": url,
            "source": source,
            "status": "captured",
            "error": None,
        }

    def key_combination(self, keys: list[str]) -> EnvState:
        keys = [PLAYWRIGHT_KEY_MAP.get(k.lower(), k) for k in keys]
        for key in keys[:-1]:
            self._page.keyboard.down(key)
        self._page.keyboard.press(keys[-1])
        for key in reversed(keys[:-1]):
            self._page.keyboard.up(key)
        return self.current_state()

    def drag_and_drop(
        self, x: int, y: int, destination_x: int, destination_y: int
    ) -> EnvState:
        self.highlight_mouse(x, y)
        self._page.mouse.move(x, y)
        self._page.wait_for_load_state()
        self._page.mouse.down()
        self._page.wait_for_load_state()
        self.highlight_mouse(destination_x, destination_y)
        self._page.mouse.move(destination_x, destination_y)
        self._page.wait_for_load_state()
        self._page.mouse.up()
        return self.current_state()

    def current_state(self) -> EnvState:
        self._page.wait_for_load_state()
        time.sleep(0.5)
        screenshot_bytes = self._page.screenshot(type="png", full_page=False)
        with self._frame_lock:
            self._frame_buffer = screenshot_bytes
        self._write_history_snapshot(screenshot_bytes)
        return EnvState(screenshot=screenshot_bytes, url=self._page.url)

    def screen_size(self) -> tuple[int, int]:
        viewport_size = self._page.viewport_size
        if viewport_size:
            return viewport_size["width"], viewport_size["height"]
        return self._screen_size

    def highlight_mouse(self, x: int, y: int):
        if not self._highlight_mouse:
            return
        self._page.evaluate(
            f"""
        () => {{
            const element_id = "playwright-feedback-circle";
            const div = document.createElement('div');
            div.id = element_id;
            div.style.pointerEvents = 'none';
            div.style.border = '4px solid red';
            div.style.borderRadius = '50%';
            div.style.width = '20px';
            div.style.height = '20px';
            div.style.position = 'fixed';
            div.style.zIndex = '9999';
            document.body.appendChild(div);

            div.hidden = false;
            div.style.left = {x} - 10 + 'px';
            div.style.top = {y} - 10 + 'px';

            setTimeout(() => {{
                div.hidden = true;
            }}, 2000);
        }}
    """
        )
        time.sleep(1)

    def _start_frame_stream(self) -> None:
        video_dir = self.video_dir()
        if not video_dir:
            return
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            return
        self._prepare_log_dirs()
        output_path = video_dir / "session_60fps.mp4"
        cmd = [
            ffmpeg_cmd, "-y",
            "-f", "image2pipe",
            "-framerate", str(FRAME_CAPTURE_FPS),
            "-vcodec", "png",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
        self._ffmpeg_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._frame_stop.clear()
        self._frame_thread = threading.Thread(
            target=self._frame_pipe_loop,
            daemon=True,
            name="frame-pipe",
        )
        self._frame_thread.start()

    def _stop_frame_stream(self) -> None:
        self._frame_stop.set()
        if self._frame_thread:
            self._frame_thread.join(timeout=5)
            self._frame_thread = None
        if self._ffmpeg_proc:
            try:
                if self._ffmpeg_proc.stdin:
                    self._ffmpeg_proc.stdin.close()
                self._ffmpeg_proc.wait(timeout=30)
            except Exception:
                self._ffmpeg_proc.kill()
            self._ffmpeg_proc = None

    def _frame_pipe_loop(self) -> None:
        interval = 1.0 / FRAME_CAPTURE_FPS
        while not self._frame_stop.wait(interval):
            with self._frame_lock:
                frame = self._frame_buffer
            if frame is None or self._ffmpeg_proc is None:
                continue
            try:
                self._ffmpeg_proc.stdin.write(frame)
            except (BrokenPipeError, OSError):
                break

    def _prepare_log_dirs(self):
        self._artifact_logger.prepare_log_dirs()

    def latest_artifact_metadata(self) -> Optional[dict]:
        return self._artifact_logger.latest_artifact_metadata()

    def record_action(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        result_summary: str | None = None,
    ) -> None:
        self._artifact_logger.record_action(
            tool=tool,
            args=args,
            result_summary=result_summary,
        )

    def history_dir(self) -> Optional[Path]:
        return self._artifact_logger.history_dir()

    def video_dir(self) -> Optional[Path]:
        return self._artifact_logger.video_dir()

    def _capture_a11y_snapshot(self, step_name: str) -> dict[str, Any]:
        a11y_source = "body_locator_aria_snapshot"
        history_dir = self.history_dir()
        if not history_dir:
            return {
                "a11y_path": None,
                "a11y_source": a11y_source,
                "a11y_capture_status": "disabled",
                "a11y_capture_error": None,
            }

        a11y_path = history_dir / f"{step_name}.a11y.yaml"
        try:
            aria_snapshot = self._page.locator("body").aria_snapshot()
            a11y_path.write_text(aria_snapshot, encoding="utf-8")
        except Exception as exc:
            return {
                "a11y_path": None,
                "a11y_source": a11y_source,
                "a11y_capture_status": "error",
                "a11y_capture_error": str(exc),
            }

        return {
            "a11y_path": a11y_path.name,
            "a11y_source": a11y_source,
            "a11y_capture_status": "captured",
            "a11y_capture_error": None,
        }

    def _write_history_snapshot(self, screenshot_bytes: bytes):
        history_dir = self.history_dir()
        if not history_dir:
            return

        self._prepare_log_dirs()
        next_step = 1
        latest_metadata = self.latest_artifact_metadata()
        if latest_metadata is not None:
            next_step = int(latest_metadata["step"]) + 1
        step_name = f"step-{next_step:04d}"
        a11y_metadata = self._capture_a11y_snapshot(step_name)
        self._artifact_logger.write_snapshot(
            screenshot_bytes=screenshot_bytes,
            url=self._page.url,
            html=self._page.content(),
            a11y_path=a11y_metadata["a11y_path"],
            metadata_extra={
                "a11y_source": a11y_metadata["a11y_source"],
                "a11y_capture_status": a11y_metadata["a11y_capture_status"],
                "a11y_capture_error": a11y_metadata["a11y_capture_error"],
            },
        )
