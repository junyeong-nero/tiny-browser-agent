import json
import time
from pathlib import Path
from typing import Any


class ArtifactLogger:
    def __init__(self, log_dir: str | None = None):
        self._log_dir = Path(log_dir) if log_dir else None
        self._history_dir = self._log_dir / "history" if self._log_dir else None
        self._video_dir = self._log_dir / "video" if self._log_dir else None
        self._history_step = 0
        self._latest_artifact_metadata: dict[str, Any] | None = None

    def prepare_log_dirs(self) -> None:
        if not self._history_dir or not self._video_dir:
            return
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._video_dir.mkdir(parents=True, exist_ok=True)

    def history_dir(self) -> Path | None:
        return self._history_dir

    def video_dir(self) -> Path | None:
        return self._video_dir

    def latest_artifact_metadata(self) -> dict[str, Any] | None:
        if self._latest_artifact_metadata is None:
            return None
        return dict(self._latest_artifact_metadata)

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
        self._history_step += 1
        step_name = f"step-{self._history_step:04d}"
        screenshot_path = self._history_dir / f"{step_name}.png"
        html_path = self._history_dir / f"{step_name}.html"
        metadata_path = self._history_dir / f"{step_name}.json"

        screenshot_path.write_bytes(screenshot_bytes)
        if html is not None:
            html_path.write_text(html, encoding="utf-8")

        metadata = {
            "step": self._history_step,
            "timestamp": time.time(),
            "url": url,
            "html_path": html_path.name if html is not None else None,
            "screenshot_path": screenshot_path.name,
            "a11y_path": a11y_path,
            "metadata_path": metadata_path.name,
            **(metadata_extra or {}),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        self._latest_artifact_metadata = metadata
        return dict(metadata)
