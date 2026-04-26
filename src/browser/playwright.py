import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional, cast

import termcolor
import playwright.sync_api
from playwright.sync_api import sync_playwright

from .aria_snapshot import AriaSnapshot, NodeInfo, build_aria_snapshot
from .artifact_logger import ArtifactLogger
from .state import BrowserState, EnvState, InteractionState, PageState, ViewportState
from .state_graph import browser_state_to_graph

FRAME_CAPTURE_FPS = 60


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
        initial_url: str = "https://www.duckduckgo.com",
        search_engine_url: str = "https://www.duckduckgo.com",
        highlight_mouse: bool = False,
        headless: bool = False,
        artifact_logger: Optional[ArtifactLogger] = None,
        allowed_upload_roots: Optional[list[str | Path]] = None,
    ):
        self._initial_url = initial_url
        self._screen_size = screen_size
        self._search_engine_url = search_engine_url
        self._highlight_mouse = highlight_mouse
        self._headless = headless
        self._artifact_logger = artifact_logger if artifact_logger is not None else ArtifactLogger()
        self._allowed_upload_roots = self._normalize_upload_roots(allowed_upload_roots)
        self._frame_buffer: bytes | None = None
        self._frame_lock = threading.Lock()
        self._frame_thread: Optional[threading.Thread] = None
        self._frame_stop = threading.Event()
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._aria_ref_map: dict[int, NodeInfo] | None = None
        self._previous_state: BrowserState | None = None
        self._pending_last_action: str | None = None

    def set_artifact_logger(self, artifact_logger: ArtifactLogger) -> None:
        """Swap the artifact logger (e.g. when starting a new session task).

        Prepares log directories on the new logger so screenshots written by the
        browser land alongside agent artifacts for the same task.
        """
        self._artifact_logger = artifact_logger
        self._artifact_logger.prepare_log_dirs()

    def _normalize_upload_roots(
        self,
        allowed_upload_roots: Optional[list[str | Path]],
    ) -> list[Path]:
        roots = allowed_upload_roots
        if roots is None:
            roots = [Path.cwd(), Path(tempfile.gettempdir())]
        return [Path(root).expanduser().resolve() for root in roots]

    def _is_allowed_upload_path(self, path: Path) -> bool:
        for root in self._allowed_upload_roots:
            try:
                path.relative_to(root)
            except ValueError:
                continue
            return True
        return False

    def reset_to_blank(self) -> None:
        """Recover from an aborted task: close popups, navigate to a blank page,
        and drop cached ARIA refs so the next task starts clean.
        """
        self._aria_ref_map = None
        try:
            for page in list(self._context.pages):
                if page is not self._page:
                    try:
                        page.close()
                    except Exception:
                        pass
            self._page.goto("about:blank")
            self._page.wait_for_load_state()
        except Exception as exc:
            termcolor.cprint(
                f"Browser reset after task failure encountered an error: {exc}",
                color="yellow",
            )

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
        self._mark_last_action("open_web_browser")
        return self.current_state()

    def click_at(self, x: int, y: int) -> EnvState:
        self._mark_last_action("click_at")
        self.highlight_mouse(x, y)
        self._page.mouse.click(x, y)
        return self._state_after_load()

    def hover_at(self, x: int, y: int) -> EnvState:
        self._mark_last_action("hover_at")
        self.highlight_mouse(x, y)
        self._page.mouse.move(x, y)
        return self._state_after_load()

    def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool = False,
        clear_before_typing: bool = True,
    ) -> EnvState:
        self._mark_last_action("type_text_at")
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
        self._mark_last_action("scroll_document")
        horizontal_scroll_amount = self.screen_size()[0] // 2
        sign = "" if direction == "right" else "-"
        self._page.evaluate(f"window.scrollBy({sign}{horizontal_scroll_amount}, 0); ")
        return self._state_after_load()

    def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> EnvState:
        self._mark_last_action("scroll_document")
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
        self._mark_last_action("scroll_at")
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
        return self._state_after_load()

    def wait_5_seconds(self) -> EnvState:
        self._mark_last_action("wait_5_seconds")
        time.sleep(5)
        return self.current_state()

    def go_back(self) -> EnvState:
        self._mark_last_action("go_back")
        self._page.go_back()
        return self._state_after_load()

    def go_forward(self) -> EnvState:
        self._mark_last_action("go_forward")
        self._page.go_forward()
        return self._state_after_load()

    def search(self) -> EnvState:
        self._mark_last_action("search")
        return self.navigate(self._search_engine_url)

    def navigate(self, url: str) -> EnvState:
        self._mark_last_action("navigate")
        normalized_url = url if url.startswith(("http://", "https://")) else "https://" + url
        self._page.goto(normalized_url)
        return self._state_after_load()

    def take_aria_snapshot(self) -> AriaSnapshot:
        """Take a fresh ARIA snapshot, assign integer refs, and cache the ref map."""
        try:
            raw_yaml = self._page.locator("body").aria_snapshot()
        except Exception as exc:
            termcolor.cprint(
                f"ARIA snapshot capture failed: {exc}",
                color="yellow",
            )
            snapshot = AriaSnapshot(text="", ref_map={}, url=self._page.url)
            self._aria_ref_map = snapshot.ref_map
            return snapshot
        snapshot = build_aria_snapshot(raw_yaml, self._page.url)
        self._aria_ref_map = snapshot.ref_map
        return snapshot

    def resolve_ref(self, ref: int) -> playwright.sync_api.Locator:
        """Resolve an integer ref to a Playwright Locator using the cached ref map."""
        if self._aria_ref_map is None:
            raise ValueError("No ARIA snapshot cached. Call take_aria_snapshot() first.")
        node = self._aria_ref_map.get(ref)
        if node is None:
            raise ValueError(f"ref {ref} is stale, request a new snapshot")
        if node.nth < 0:
            raise ValueError(f"NodeInfo.nth must be >= 0, got {node.nth} for ref {ref}")
        # Skip name param if empty to avoid selector matching empty name attribute
        if node.name:
            locator = self._page.get_by_role(node.role, name=node.name)  # type: ignore[arg-type]
        else:
            locator = self._page.get_by_role(node.role)
        return locator.nth(node.nth)

    def reload_page(self) -> EnvState:
        self._mark_last_action("reload_page")
        self._page.reload()
        return self._state_after_load()

    def upload_file(self, x: int, y: int, path: str) -> EnvState:
        self._mark_last_action("upload_file")
        raw_path = Path(path).expanduser()
        if not raw_path.is_absolute():
            raise ValueError(f"upload_file requires an absolute path; got: {path}")
        if not raw_path.exists():
            raise FileNotFoundError(f"upload_file target does not exist: {path}")
        resolved_path = raw_path.resolve(strict=True)
        if not self._is_allowed_upload_path(resolved_path):
            roots = ", ".join(str(root) for root in self._allowed_upload_roots)
            raise PermissionError(
                f"upload_file target is outside allowed upload roots: {resolved_path}. "
                f"Allowed roots: {roots}"
            )

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
        self._mark_last_action("key_combination")
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
        self._mark_last_action("drag_and_drop")
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

    def _state_after_load(self) -> EnvState:
        self._page.wait_for_load_state()
        return self.current_state()

    def current_state(self) -> EnvState:
        self._page.wait_for_load_state()
        time.sleep(0.5)
        screenshot_bytes = self._page.screenshot(type="png", full_page=False)
        with self._frame_lock:
            self._frame_buffer = screenshot_bytes
        viewport_width, viewport_height = self.screen_size()
        scroll_x, scroll_y = self._scroll_position()
        available_refs = sorted(self._aria_ref_map.keys()) if self._aria_ref_map else []
        last_action = self._pending_last_action
        self._pending_last_action = None
        state = EnvState(
            page=PageState(
                url=self._page.url,
                title=self._page.title(),
            ),
            viewport=ViewportState(
                screenshot=screenshot_bytes,
                width=viewport_width,
                height=viewport_height,
                scroll_x=scroll_x,
                scroll_y=scroll_y,
            ),
            interaction=InteractionState(
                focused_element=self._focused_element(),
                available_refs=available_refs,
                last_action=last_action,
            ),
        )
        previous_state = self._previous_state
        artifact_metadata = self._write_history_snapshot(state, previous_state)
        self._previous_state = state
        if artifact_metadata is None:
            return state
        return EnvState(
            page=state.page.model_copy(
                update={
                    "html_path": self._artifact_path(artifact_metadata, "html_path"),
                    "a11y_path": self._artifact_path(artifact_metadata, "a11y_path"),
                }
            ),
            viewport=state.viewport,
            interaction=state.interaction,
        )

    def _scroll_position(self) -> tuple[int, int]:
        position = self._page.evaluate(
            "() => ({ scrollX: window.scrollX, scrollY: window.scrollY })"
        )
        if not isinstance(position, dict):
            return 0, 0
        return int(position.get("scrollX", 0)), int(position.get("scrollY", 0))

    def _focused_element(self) -> str | None:
        focused = self._page.evaluate(
            """
            () => {
              const el = document.activeElement;
              if (!el || el === document.body) return null;
              const tag = el.tagName ? el.tagName.toLowerCase() : '';
              const id = el.id ? `#${el.id}` : '';
              const name = el.getAttribute && el.getAttribute('name')
                ? `[name=${el.getAttribute('name')}]`
                : '';
              return `${tag}${id}${name}` || null;
            }
            """
        )
        return focused if isinstance(focused, str) else None

    def _artifact_path(self, metadata: dict[str, Any] | None, key: str) -> str | None:
        if metadata is None:
            return None
        value = metadata.get(key)
        return value if isinstance(value, str) else None

    def _mark_last_action(self, action_name: str) -> None:
        if self._pending_last_action is None:
            self._pending_last_action = action_name

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
            stdin = self._ffmpeg_proc.stdin
            if stdin is None:
                break
            try:
                stdin.write(frame)
            except (BrokenPipeError, OSError):
                break

    def _prepare_log_dirs(self):
        self._artifact_logger.prepare_log_dirs()

    def latest_artifact_metadata(self) -> Optional[dict]:
        return self._artifact_logger.latest_artifact_metadata()

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

    def _write_history_snapshot(
        self,
        state: BrowserState,
        previous_state: BrowserState | None = None,
    ) -> dict[str, Any] | None:
        history_dir = self.history_dir()
        if not history_dir:
            return None

        self._prepare_log_dirs()
        next_step = 1
        latest_metadata = self.latest_artifact_metadata()
        if latest_metadata is not None:
            next_step = int(latest_metadata["step"]) + 1
        step_name = f"step-{next_step:04d}"
        a11y_metadata = self._capture_a11y_snapshot(step_name)
        state_for_metadata = state.model_copy(
            update={
                "page": state.page.model_copy(
                    update={
                        "html_path": f"{step_name}.html",
                        "a11y_path": a11y_metadata["a11y_path"],
                    }
                )
            }
        )
        return self._artifact_logger.write_snapshot(
            screenshot_bytes=state.viewport.screenshot,
            url=state.page.url,
            html=self._page.content(),
            a11y_path=a11y_metadata["a11y_path"],
            metadata_extra={
                "a11y_source": a11y_metadata["a11y_source"],
                "a11y_capture_status": a11y_metadata["a11y_capture_status"],
                "a11y_capture_error": a11y_metadata["a11y_capture_error"],
                "state_graph": browser_state_to_graph(state_for_metadata, previous_state),
            },
        )
