"""Internal recording helpers for PlaywrightBrowser artifacts and clips."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .artifact_logger import ArtifactLogger
from .gif import build_high_quality_gif_filter


class BrowserRecordingHelper:
    """Owns frame streaming and per-action recording state.

    The public browser facade keeps compatibility wrappers for tests and callers;
    this helper centralizes the stateful recording implementation.
    """

    def __init__(self, *, artifact_logger: ArtifactLogger, subprocess_module: Any, shutil_module: Any):
        self.artifact_logger = artifact_logger
        self._subprocess = subprocess_module
        self._shutil = shutil_module
        self.frame_buffer: bytes | None = None
        self.frame_lock = threading.Lock()
        self._frame_thread: Optional[threading.Thread] = None
        self._frame_stop = threading.Event()
        self._ffmpeg_proc: Any | None = None
        self._action_cdp_session: Any | None = None
        self._action_capture_frames: list[tuple[float, bytes]] | None = None
        self._action_capture_lock = threading.Lock()
        self._action_capture_started_at: float | None = None

    def set_artifact_logger(self, artifact_logger: ArtifactLogger) -> None:
        self.artifact_logger = artifact_logger

    def history_dir(self) -> Optional[Path]:
        return self.artifact_logger.history_dir()

    def video_dir(self) -> Optional[Path]:
        return self.artifact_logger.video_dir()

    def latest_artifact_metadata(self) -> Optional[dict]:
        return self.artifact_logger.latest_artifact_metadata()

    def prepare_log_dirs(self) -> None:
        self.artifact_logger.prepare_log_dirs()

    def update_frame_buffer(self, frame: bytes) -> None:
        with self.frame_lock:
            self.frame_buffer = frame

    def start_frame_stream(self, *, fps: int) -> None:
        video_dir = self.video_dir()
        if not video_dir:
            return
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or self._shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            return
        self.prepare_log_dirs()
        output_path = video_dir / "session_60fps.mp4"
        cmd = [
            ffmpeg_cmd, "-y",
            "-f", "image2pipe",
            "-framerate", str(fps),
            "-vcodec", "png",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
        self._ffmpeg_proc = self._subprocess.Popen(
            cmd,
            stdin=self._subprocess.PIPE,
            stdout=self._subprocess.DEVNULL,
            stderr=self._subprocess.DEVNULL,
        )
        self._frame_stop.clear()
        self._frame_thread = threading.Thread(
            target=self._frame_pipe_loop,
            args=(fps,),
            daemon=True,
            name="frame-pipe",
        )
        self._frame_thread.start()

    def stop_frame_stream(self) -> None:
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
                try:
                    self._ffmpeg_proc.wait(timeout=5)
                except Exception:
                    pass
            self._ffmpeg_proc = None

    def _frame_pipe_loop(self, fps: int) -> None:
        interval = 1.0 / fps
        while not self._frame_stop.wait(interval):
            with self.frame_lock:
                frame = self.frame_buffer
            if frame is None or self._ffmpeg_proc is None:
                continue
            stdin = self._ffmpeg_proc.stdin
            if stdin is None:
                break
            try:
                stdin.write(frame)
            except (BrokenPipeError, OSError):
                break

    def begin_action_capture(self, *, page: Any, context: Any) -> None:
        if not self.history_dir():
            return
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or self._shutil.which("ffmpeg")
        if not ffmpeg_cmd or page is None or context is None:
            return
        with self._action_capture_lock:
            self._action_capture_frames = []
            self._action_capture_started_at = time.time()
        try:
            cdp_session = context.new_cdp_session(page)

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

    def end_action_capture(self, *, persist: bool = True) -> dict[str, Any] | None:
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

        if not persist:
            return None

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
        sampled_frames = self.sample_action_frames(captured_frames, max_frames=60)
        if sampled_frames:
            metadata_updates["action_gif_frame_count"] = len(sampled_frames)
        clip_name = self.write_action_clip_gif(sampled_frames, metadata)
        if clip_name:
            metadata_updates["action_clip_gif_path"] = clip_name
        self.merge_latest_metadata(metadata_updates)
        return metadata_updates

    @staticmethod
    def sample_action_frames(
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

    @staticmethod
    def action_gif_input_fps(frames: list[tuple[float, bytes]]) -> float:
        if len(frames) < 2:
            return 20.0
        duration = max(frames[-1][0] - frames[0][0], 0.001)
        return max(0.5, min(60.0, (len(frames) - 1) / duration))

    def write_action_clip_gif(self, frames: list[tuple[float, bytes]], metadata: dict[str, Any]) -> str | None:
        if len(frames) < 2:
            return None
        history_dir = self.history_dir()
        if not history_dir:
            return None
        ffmpeg_cmd = os.getenv("COMPUTER_USE_FFMPEG_COMMAND") or self._shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            return None
        step = metadata.get("step")
        if not isinstance(step, int):
            return None
        output_path = history_dir / f"step-{step:04d}-action.gif"
        input_fps = self.action_gif_input_fps(frames)
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
            build_high_quality_gif_filter("[0:v]"),
            str(output_path),
        ]
        try:
            proc = self._subprocess.Popen(
                cmd,
                stdin=self._subprocess.PIPE,
                stdout=self._subprocess.DEVNULL,
                stderr=self._subprocess.DEVNULL,
            )
            assert proc.stdin is not None
            for _timestamp, frame in frames:
                proc.stdin.write(frame)
            proc.stdin.close()
            proc.wait(timeout=20)
        except Exception:
            return None
        return output_path.name if output_path.is_file() else None

    def merge_latest_metadata(self, updates: dict[str, Any]) -> None:
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
        latest = getattr(self.artifact_logger, "_latest_artifact_metadata", None)
        if isinstance(latest, dict):
            latest.update(updates)
