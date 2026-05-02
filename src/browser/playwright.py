import base64
import json
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

if os.getenv("USE_PATCHRIGHT") == "1":
    try:
        import patchright.sync_api as playwright_sync_module  # type: ignore[import-not-found]
    except ImportError:
        import playwright.sync_api as playwright_sync_module
else:
    import playwright.sync_api as playwright_sync_module

playwright = type(sys)("playwright")  # placeholder so existing `playwright.sync_api.X` refs resolve
playwright.sync_api = playwright_sync_module  # type: ignore[attr-defined]
sync_playwright = playwright_sync_module.sync_playwright

from .aria_snapshot import AriaSnapshot, NodeInfo, build_aria_snapshot
from .artifact_logger import ArtifactLogger
from .state import BrowserState, EnvState, InteractionState, PageState, ViewportState
from .state_graph import browser_state_to_graph

FRAME_CAPTURE_FPS = 60


PLAYWRIGHT_INSTALL_HINT = (
    "Playwright browser binaries are missing. Run "
    "`uv run playwright install chromium` and retry."
)

_STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'plugins', {
      get: () => [
        { name: 'Chrome PDF Plugin' },
        { name: 'Chrome PDF Viewer' },
        { name: 'Native Client' },
      ],
    });
  } catch (e) {}
  try {
    window.chrome = window.chrome || { runtime: {}, app: {}, csi: () => {}, loadTimes: () => {} };
  } catch (e) {}
  try {
    const origQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (origQuery) {
      window.navigator.permissions.query = (params) =>
        params && params.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission })
          : origQuery(params);
    }
  } catch (e) {}
  try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (parameter) {
      if (parameter === 37445) return 'Intel Inc.';
      if (parameter === 37446) return 'Intel Iris OpenGL Engine';
      return getParameter.call(this, parameter);
    };
  } catch (e) {}
})();
"""


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
        channel: Optional[str] = None,
        user_agent: Optional[str] = None,
        locale: Optional[str] = None,
        timezone_id: Optional[str] = None,
        proxy: Optional[dict[str, str]] = None,
        storage_state_path: Optional[str | Path] = None,
        stealth: bool = False,
        extra_http_headers: Optional[dict[str, str]] = None,
    ):
        self._initial_url = initial_url
        self._screen_size = screen_size
        self._search_engine_url = search_engine_url
        self._highlight_mouse = highlight_mouse
        self._headless = headless
        self._artifact_logger = artifact_logger if artifact_logger is not None else ArtifactLogger()
        self._allowed_upload_roots = self._normalize_upload_roots(allowed_upload_roots)
        self._channel = channel
        self._user_agent = user_agent
        self._locale = locale
        self._timezone_id = timezone_id
        self._proxy = proxy
        self._storage_state_path = Path(storage_state_path).expanduser() if storage_state_path else None
        self._stealth = stealth
        self._extra_http_headers = extra_http_headers
        self._frame_buffer: bytes | None = None
        self._frame_lock = threading.Lock()
        self._frame_thread: Optional[threading.Thread] = None
        self._frame_stop = threading.Event()
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._action_cdp_session: Any | None = None
        self._action_capture_frames: list[tuple[float, bytes]] | None = None
        self._action_capture_lock = threading.Lock()
        self._action_capture_started_at: float | None = None
        self._aria_ref_map: dict[int, NodeInfo] | None = None
        self._aria_ref_target_map: dict[int, Any] | None = None
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
        self._aria_ref_target_map = None
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

    def _goto_or_blank(self, url: str, *, context: str) -> None:
        """Navigate to ``url`` and keep the browser usable if navigation fails."""
        try:
            self._page.goto(url)
        except playwright.sync_api.Error as exc:
            termcolor.cprint(
                f"{context} navigation failed for {url}: {exc}. "
                "Continuing from about:blank.",
                color="yellow",
            )
            try:
                self._page.goto("about:blank")
            except playwright.sync_api.Error as fallback_exc:
                termcolor.cprint(
                    "Fallback navigation to about:blank also failed; "
                    f"continuing with the current browser page: {fallback_exc}",
                    color="yellow",
                )

    def _handle_new_page(self, new_page: playwright.sync_api.Page):
        self._page = new_page
        self._page.wait_for_load_state()

    def __enter__(self):
        print("Creating session...")
        self._prepare_log_dirs()
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self._headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--no-default-browser-check",
                "--no-first-run",
            ],
        }
        if self._channel:
            launch_kwargs["channel"] = self._channel
        if self._proxy:
            launch_kwargs["proxy"] = self._proxy
        try:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
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
        if self._user_agent:
            context_kwargs["user_agent"] = self._user_agent
        if self._locale:
            context_kwargs["locale"] = self._locale
        if self._timezone_id:
            context_kwargs["timezone_id"] = self._timezone_id
        if self._extra_http_headers:
            context_kwargs["extra_http_headers"] = self._extra_http_headers
        if self._storage_state_path and self._storage_state_path.is_file():
            context_kwargs["storage_state"] = str(self._storage_state_path)
        video_dir = self.video_dir()
        if video_dir:
            context_kwargs["record_video_dir"] = str(video_dir)
            context_kwargs["record_video_size"] = viewport_size
        self._context = self._browser.new_context(**context_kwargs)
        if self._stealth:
            self._context.add_init_script(_STEALTH_INIT_SCRIPT)
        self._page = self._context.new_page()
        self._goto_or_blank(self._initial_url, context="Initial page")
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
            if self._storage_state_path:
                try:
                    self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    self._context.storage_state(path=str(self._storage_state_path))
                except Exception as exc:
                    termcolor.cprint(
                        f"Failed to persist storage_state to {self._storage_state_path}: {exc}",
                        color="yellow",
                    )
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
        self._goto_or_blank(normalized_url, context="Page")
        return self._state_after_load()

    def take_aria_snapshot(self) -> AriaSnapshot:
        """Take a fresh ARIA snapshot, assign integer refs, and cache the ref map."""
        try:
            snapshot, _source, _frame_count = self._capture_frame_aware_aria_snapshot()
        except Exception as exc:
            termcolor.cprint(
                f"ARIA snapshot capture failed: {exc}",
                color="yellow",
            )
            snapshot = AriaSnapshot(text="", ref_map={}, url=self._page.url)
            self._aria_ref_target_map = {}
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
        target = self._page
        if self._aria_ref_target_map is not None:
            target = self._aria_ref_target_map.get(ref, self._page)
        role_target = cast(Any, target)
        if node.name:
            locator = role_target.get_by_role(node.role, name=node.name)
        else:
            locator = role_target.get_by_role(node.role)
        return locator.nth(node.nth)

    def reload_page(self) -> EnvState:
        self._mark_last_action("reload_page")
        self._page.reload()
        return self._state_after_load()

    def switch_to_next_tab(self) -> EnvState:
        self._mark_last_action("switch_to_next_tab")
        self._switch_tab(direction=1)
        return self._state_after_load()

    def switch_to_previous_tab(self) -> EnvState:
        self._mark_last_action("switch_to_previous_tab")
        self._switch_tab(direction=-1)
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
        try:
            snapshot, source, frame_count = self._capture_frame_aware_aria_snapshot()
        except Exception as exc:
            return {
                "tree": None,
                "url": self._page.url,
                "source": "body_locator_aria_snapshot",
                "status": "error",
                "error": str(exc),
                "frame_count": 0,
            }
        self._aria_ref_map = snapshot.ref_map
        return {
            "tree": snapshot.text,
            "url": self._page.url,
            "source": source,
            "status": "captured",
            "error": None,
            "frame_count": frame_count,
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


    def begin_action_capture(self) -> None:
        """Best-effort capture of frames emitted while a browser action runs."""
        if not self.history_dir():
            return
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or shutil.which("ffmpeg")
        if not ffmpeg_cmd or self._page is None or self._context is None:
            return
        with self._action_capture_lock:
            self._action_capture_frames = []
            self._action_capture_started_at = time.time()
        try:
            cdp_session = self._context.new_cdp_session(self._page)

            def on_frame(params: dict[str, Any]) -> None:
                data = params.get("data")
                session_id = params.get("sessionId")
                if session_id is not None:
                    try:
                        cdp_session.send("Page.screencastFrameAck", {"sessionId": session_id})
                    except Exception:
                        pass
                if not isinstance(data, str):
                    return
                try:
                    frame = base64.b64decode(data)
                except Exception:
                    return
                frame_ts = time.time()
                metadata = params.get("metadata")
                if isinstance(metadata, dict) and isinstance(metadata.get("timestamp"), (int, float)):
                    # CDP timestamps are monotonic seconds; keep wall-clock time for
                    # consistency with action_started_at/action_ended_at.
                    frame_ts = time.time()
                with self._action_capture_lock:
                    frames = self._action_capture_frames
                    if frames is not None and len(frames) < 600:
                        frames.append((frame_ts, frame))

            cdp_session.on("Page.screencastFrame", on_frame)
            cdp_session.send("Page.startScreencast", {"format": "png", "quality": 80, "everyNthFrame": 1})
            self._action_cdp_session = cdp_session
        except Exception:
            with self._action_capture_lock:
                self._action_capture_frames = None
                self._action_capture_started_at = None
            self._action_cdp_session = None

    def end_action_capture(self) -> dict[str, Any] | None:
        cdp_session = self._action_cdp_session
        if cdp_session is not None:
            try:
                cdp_session.send("Page.stopScreencast")
            except Exception:
                pass
            self._action_cdp_session = None

        with self._action_capture_lock:
            captured_frames = list(self._action_capture_frames or [])
            started_at = self._action_capture_started_at
            self._action_capture_frames = None
            self._action_capture_started_at = None

        metadata = self.latest_artifact_metadata()
        history_dir = self.history_dir()
        if not metadata or not history_dir:
            return None

        ended_at = time.time()
        metadata_updates: dict[str, Any] = {
            "action_started_at": started_at,
            "action_ended_at": ended_at,
            "action_duration_ms": int((ended_at - started_at) * 1000) if started_at else None,
            "action_capture_frame_count": len(captured_frames),
        }
        sampled_frames = self._sample_action_frames(captured_frames, max_frames=60)
        if sampled_frames:
            metadata_updates["action_gif_frame_count"] = len(sampled_frames)
        clip_name = self._write_action_clip_gif(sampled_frames, metadata)
        if clip_name:
            metadata_updates["action_clip_gif_path"] = clip_name
        self._merge_latest_metadata(metadata_updates)
        return metadata_updates

    def _sample_action_frames(
        self,
        frames: list[tuple[float, bytes]],
        *,
        max_frames: int,
    ) -> list[tuple[float, bytes]]:
        if len(frames) <= max_frames:
            return frames
        if max_frames <= 1:
            return frames[:1]
        last_index = len(frames) - 1
        selected: list[tuple[float, bytes]] = []
        seen_indices: set[int] = set()
        for out_index in range(max_frames):
            source_index = round(out_index * last_index / (max_frames - 1))
            if source_index in seen_indices:
                continue
            seen_indices.add(source_index)
            selected.append(frames[source_index])
        return selected

    def _action_gif_input_fps(self, frames: list[tuple[float, bytes]]) -> float:
        if len(frames) < 2:
            return 20.0
        duration = max(frames[-1][0] - frames[0][0], 0.001)
        return max(0.5, min(60.0, (len(frames) - 1) / duration))

    def _write_action_clip_gif(self, frames: list[tuple[float, bytes]], metadata: dict[str, Any]) -> str | None:
        if len(frames) < 2:
            return None
        history_dir = self.history_dir()
        if not history_dir:
            return None
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            return None
        step = metadata.get("step")
        if not isinstance(step, int):
            return None
        output_path = history_dir / f"step-{step:04d}-action.gif"
        input_fps = self._action_gif_input_fps(frames)
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-f",
            "image2pipe",
            "-framerate",
            f"{input_fps:.3f}",
            "-vcodec",
            "png",
            "-i",
            "pipe:0",
            "-filter_complex",
            (
                "[0:v]scale=640:-1:flags=lanczos,split[p0][p1];"
                "[p0]palettegen=max_colors=256:stats_mode=diff:reserve_transparent=0[p];"
                "[p1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
            ),
            str(output_path),
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            assert proc.stdin is not None
            for _timestamp, frame in frames:
                proc.stdin.write(frame)
            proc.stdin.close()
            proc.wait(timeout=20)
        except Exception:
            return None
        return output_path.name if output_path.is_file() else None

    def _merge_latest_metadata(self, updates: dict[str, Any]) -> None:
        metadata = self.latest_artifact_metadata()
        history_dir = self.history_dir()
        if not metadata or not history_dir:
            return
        metadata_path_value = metadata.get("metadata_path")
        if not isinstance(metadata_path_value, str):
            return
        metadata_path = history_dir / metadata_path_value
        if not metadata_path.is_file():
            return
        try:
            current = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(current, dict):
            return
        current.update(updates)
        metadata_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        # Keep the logger's public latest metadata in sync by updating through the
        # private field only when present; this avoids another public mutator just
        # for the browser-owned enrichment path.
        latest = getattr(self._artifact_logger, "_latest_artifact_metadata", None)
        if isinstance(latest, dict):
            latest.update(updates)

    def _prepare_log_dirs(self):
        self._artifact_logger.prepare_log_dirs()

    def _switch_tab(self, direction: int) -> None:
        pages = list(self._context.pages)
        if not pages:
            return
        try:
            current_index = pages.index(self._page)
        except ValueError:
            current_index = 0
        next_index = (current_index + direction) % len(pages)
        self._page = pages[next_index]
        self._page.bring_to_front()

    def latest_artifact_metadata(self) -> Optional[dict]:
        return self._artifact_logger.latest_artifact_metadata()

    def history_dir(self) -> Optional[Path]:
        return self._artifact_logger.history_dir()

    def video_dir(self) -> Optional[Path]:
        return self._artifact_logger.video_dir()

    def _aria_snapshot_targets(self) -> list[Any]:
        frames = getattr(self._page, "frames", None)
        if isinstance(frames, list) and frames:
            return frames
        return [self._page]

    def _capture_frame_aware_aria_snapshot(self) -> tuple[AriaSnapshot, str, int]:
        targets = self._aria_snapshot_targets()
        multi_frame = len(targets) > 1
        combined_lines: list[str] = []
        combined_ref_map: dict[int, NodeInfo] = {}
        target_map: dict[int, Any] = {}
        ref_offset = 0
        captured_frame_count = 0

        for index, target in enumerate(targets, start=1):
            target_url = getattr(target, "url", self._page.url)
            raw_yaml = target.locator("body").aria_snapshot()
            snapshot = build_aria_snapshot(raw_yaml, target_url, ref_offset=ref_offset)
            if multi_frame:
                combined_lines.append(f"Frame {index}: {target_url}")
                if snapshot.text:
                    combined_lines.extend(
                        f"  {line}" if line else line
                        for line in snapshot.text.splitlines()
                    )
            elif snapshot.text:
                combined_lines.extend(snapshot.text.splitlines())
            combined_ref_map.update(snapshot.ref_map)
            target_map.update({ref: target for ref in snapshot.ref_map})
            ref_offset += len(snapshot.ref_map)
            captured_frame_count += 1

        self._aria_ref_target_map = target_map
        return (
            AriaSnapshot(
                text="\n".join(combined_lines),
                ref_map=combined_ref_map,
                url=self._page.url,
            ),
            "frame_locator_aria_snapshot" if multi_frame else "body_locator_aria_snapshot",
            captured_frame_count,
        )

    def _capture_a11y_snapshot(self, step_name: str) -> dict[str, Any]:
        history_dir = self.history_dir()
        if not history_dir:
            return {
                "a11y_path": None,
                "a11y_source": "body_locator_aria_snapshot",
                "a11y_capture_status": "disabled",
                "a11y_capture_error": None,
            }

        a11y_path = history_dir / f"{step_name}.a11y.yaml"
        try:
            snapshot, a11y_source, _frame_count = self._capture_frame_aware_aria_snapshot()
            a11y_path.write_text(snapshot.text, encoding="utf-8")
        except Exception as exc:
            return {
                "a11y_path": None,
                "a11y_source": "body_locator_aria_snapshot",
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
