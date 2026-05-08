import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


class ArtifactLogger:
    def __init__(
        self,
        log_dir: str | None = None,
        *,
        history_enabled: bool | None = None,
        video_enabled: bool = False,
    ):
        self._log_dir = Path(log_dir) if log_dir else None
        if history_enabled is None:
            history_enabled = self._log_dir is not None
        history_active = self._log_dir is not None and history_enabled
        video_active = self._log_dir is not None and video_enabled
        self._history_dir = self._log_dir / "history" if history_active else None
        self._video_dir = self._log_dir / "video" if video_active else None
        self._actions_file = self._log_dir / "actions.jsonl" if history_active else None
        self._events_file = self._log_dir / "events.jsonl" if history_active else None
        self._session_file = self._log_dir / "session.json" if history_active else None
        self._history_step = 0
        self._latest_artifact_metadata: dict[str, Any] | None = None

    def prepare_log_dirs(self) -> None:
        if self._history_dir:
            self._history_dir.mkdir(parents=True, exist_ok=True)
        if self._video_dir:
            self._video_dir.mkdir(parents=True, exist_ok=True)

    def history_dir(self) -> Path | None:
        return self._history_dir

    def video_dir(self) -> Path | None:
        return self._video_dir

    def session_id(self) -> str | None:
        return self._log_dir.name if self._log_dir else None

    def latest_artifact_metadata(self) -> dict[str, Any] | None:
        if self._latest_artifact_metadata is None:
            return None
        return dict(self._latest_artifact_metadata)

    def _write_action_gif(
        self,
        *,
        before_path: Path | None,
        after_path: Path,
        step_name: str,
    ) -> str | None:
        if before_path is None or not before_path.is_file():
            return None
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            return None
        gif_path = self._history_dir / f"{step_name}.gif" if self._history_dir else None
        if gif_path is None:
            return None
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-loop",
            "1",
            "-t",
            "0.85",
            "-i",
            str(before_path),
            "-loop",
            "1",
            "-t",
            "1.15",
            "-i",
            str(after_path),
            "-filter_complex",
            (
                "[0:v][1:v]concat=n=2:v=1:a=0,"
                "fps=2,scale=640:-1:flags=lanczos,split[p0][p1];"
                "[p0]palettegen=max_colors=256:stats_mode=diff:reserve_transparent=0[p];"
                "[p1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
            ),
            str(gif_path),
        ]
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=15,
            )
        except Exception:
            return None
        return gif_path.name if gif_path.is_file() else None

    def record_event(self, event: dict[str, Any]) -> None:
        """Append a replayable UI event to events.jsonl."""
        if not self._events_file:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        entry = {"ts": time.time(), **event}
        with self._events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def record_session_meta(self, meta: dict[str, Any]) -> None:
        """Write session metadata once for replay session listings."""
        if not self._session_file:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        if self._session_file.exists():
            return
        self._session_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    def record_action(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        result_summary: str | None = None,
    ) -> None:
        if not self._actions_file:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        entry = {
            "timestamp": time.time(),
            "tool": tool,
            "args": args,
            "result_summary": result_summary,
        }
        with self._actions_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_snapshot(
        self,
        *,
        screenshot_bytes: bytes,
        url: str,
        html: str | None,
        a11y_path: str | None,
        metadata_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self._history_dir:
            self._latest_artifact_metadata = None
            return None

        self.prepare_log_dirs()
        previous_metadata = self._latest_artifact_metadata or {}
        self._history_step += 1
        step_name = f"step-{self._history_step:04d}"
        screenshot_path = self._history_dir / f"{step_name}.png"
        html_path = self._history_dir / f"{step_name}.html"
        metadata_path = self._history_dir / f"{step_name}.json"

        screenshot_path.write_bytes(screenshot_bytes)
        if html is not None:
            html_path.write_text(html, encoding="utf-8")
        before_screenshot_name = previous_metadata.get("screenshot_path")
        before_screenshot_path = (
            self._history_dir / before_screenshot_name
            if isinstance(before_screenshot_name, str)
            else None
        )
        action_gif_path = self._write_action_gif(
            before_path=before_screenshot_path,
            after_path=screenshot_path,
            step_name=step_name,
        )

        metadata = {
            "step": self._history_step,
            "timestamp": time.time(),
            "url": url,
            "html_path": html_path.name if html is not None else None,
            "screenshot_path": screenshot_path.name,
            "before_screenshot_path": before_screenshot_name,
            "after_screenshot_path": screenshot_path.name,
            "action_gif_path": action_gif_path,
            "a11y_path": a11y_path,
            "metadata_path": metadata_path.name,
            "before_metadata_path": previous_metadata.get("metadata_path"),
            "after_metadata_path": metadata_path.name,
            **(metadata_extra or {}),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        self._latest_artifact_metadata = metadata
        return dict(metadata)
