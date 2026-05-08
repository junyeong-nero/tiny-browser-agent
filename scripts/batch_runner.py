#!/usr/bin/env python3
"""Run Hugging Face web-agent benchmark tasks through the local browser agent in parallel.

The script intentionally uses only the Python standard library so it can run in
this repository without adding a Hugging Face dependency. It reads rows from the
Hugging Face datasets-server API and launches commands like:

    uv run main.py --planner "<task>"

Each task gets its own stdout/stderr files plus a JSONL summary record.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATASET = "convergence-ai/WebVoyager2025Valid"
DEFAULT_SPLIT = "test"
DEFAULT_CONFIG = "default"
DATASET_DEFAULTS: dict[str, dict[str, str]] = {
    DEFAULT_DATASET: {"config": DEFAULT_CONFIG, "split": DEFAULT_SPLIT, "task_field": "task"},
    "junyeong-nero/korean-online-mind2web": {"config": DEFAULT_CONFIG, "split": "train", "task_field": "task"},
}
TASK_FIELD_CANDIDATES = ("task", "prompt", "task_description", "confirmed_task", "task_en")
URL_FIELD_CANDIDATES = ("web", "url", "initial_url", "website")
ID_FIELD_CANDIDATES = ("id", "task_id", "annotation_id")
DATASETS_SERVER = "https://datasets-server.huggingface.co/rows"
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class TaskRow:
    index: int
    task: str
    metadata: dict[str, Any]

    @property
    def task_id(self) -> str:
        if isinstance(self.metadata, dict):
            for field in ID_FIELD_CANDIDATES:
                raw_id = self.metadata.get(field)
                if raw_id:
                    return str(raw_id)
        return f"row-{self.index}"

    @property
    def initial_url(self) -> str | None:
        if not isinstance(self.metadata, dict):
            return None
        for field in URL_FIELD_CANDIDATES:
            raw_url = self.metadata.get(field)
            normalized = _normalize_url(raw_url)
            if normalized:
                return normalized
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load web-agent benchmark tasks from Hugging Face datasets-server "
            "and run `uv run main.py --planner <task>` in parallel."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Hugging Face dataset name.")
    parser.add_argument(
        "--config",
        default=None,
        help="Dataset config name. Defaults to a dataset-specific preset when known, else 'default'.",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Dataset split name. Defaults to a dataset-specific preset when known, else 'test'.",
    )
    parser.add_argument("--offset", type=int, default=0, help="First dataset row offset to run.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of tasks to run.")
    parser.add_argument("--workers", type=int, default=2, help="Number of parallel subprocesses.")
    parser.add_argument(
        "--task-field",
        default=None,
        help=(
            "Dataset column containing the query text. Use 'auto' to try common fields "
            f"({', '.join(TASK_FIELD_CANDIDATES)}). Defaults to a dataset-specific preset when known."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for per-task logs and summary.jsonl. Defaults to logs/<dataset-name>/<timestamp>.",
    )
    parser.add_argument("--timeout", type=float, default=None, help="Per-task timeout in seconds.")
    parser.add_argument(
        "--headless",
        choices=("True", "False"),
        default="True",
        help="Value forwarded to main.py --headless.",
    )
    parser.add_argument("--grounding", choices=("vision", "text", "mixed"), default=None)
    parser.add_argument("--model", default=None, help="Optional model override forwarded to main.py.")
    parser.add_argument(
        "--log-agent",
        action="store_true",
        help="Forward --log to main.py so each browser-agent run records trajectory and replay artifacts.",
    )
    parser.add_argument(
        "--video-agent",
        action="store_true",
        help="Forward --video to main.py so each browser-agent run records .webm/.mp4 video artifacts.",
    )
    parser.add_argument(
        "--metadata-initial-url",
        action="store_true",
        help="Forward a URL-like dataset field (web, website, url, initial_url) as --initial_url when present.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Additional argument forwarded to main.py. Repeat for multiple args, e.g. --extra-arg=--highlight_mouse.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands and write summary records without executing subprocesses.",
    )
    args = parser.parse_args(argv)
    _apply_dataset_defaults(args)
    return args


def _apply_dataset_defaults(args: argparse.Namespace) -> None:
    preset = DATASET_DEFAULTS.get(args.dataset, {})
    args.config = args.config or preset.get("config", DEFAULT_CONFIG)
    args.split = args.split or preset.get("split", DEFAULT_SPLIT)
    args.task_field = args.task_field or preset.get("task_field", "auto")


def fetch_tasks(
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int,
    limit: int,
    task_field: str,
) -> list[TaskRow]:
    if offset < 0:
        raise ValueError("--offset must be >= 0")
    if limit < 1:
        raise ValueError("--limit must be >= 1")

    rows: list[TaskRow] = []
    next_offset = offset
    remaining = limit

    while remaining > 0:
        page_size = min(MAX_PAGE_SIZE, remaining)
        payload = _request_rows(dataset=dataset, config=config, split=split, offset=next_offset, length=page_size)
        page_rows = payload.get("rows", [])
        if not page_rows:
            break

        for item in page_rows:
            row_index = int(item.get("row_idx", next_offset + len(rows)))
            row = item.get("row", {})
            if not isinstance(row, dict):
                raise ValueError(f"Row {row_index} is not an object: {row!r}")
            task, selected_task_field = _extract_task(row, task_field)
            if task is None:
                raise ValueError(f"Row {row_index} does not contain a non-empty task field: {row!r}")
            rows.append(
                TaskRow(
                    index=row_index,
                    task=task,
                    metadata=_extract_metadata(row, task_field=selected_task_field),
                )
            )

        fetched = len(page_rows)
        if fetched < page_size:
            break
        next_offset += fetched
        remaining -= fetched

    return rows


def _extract_task(row: dict[str, Any], task_field: str) -> tuple[str | None, str | None]:
    fields = TASK_FIELD_CANDIDATES if task_field == "auto" else (task_field,)
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip(), field
    return None, None


def _extract_metadata(row: dict[str, Any], *, task_field: str | None) -> dict[str, Any]:
    metadata = _parse_metadata(row.get("metadata"))
    for field, value in row.items():
        if field == "metadata" or field == task_field:
            continue
        metadata[field] = _parse_structured_value(value)
    return metadata


def _parse_structured_value(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    text = value.strip()
    if not text.startswith(("{", "[")):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return value


def _normalize_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.startswith(("http://", "https://")):
        return text
    if "." in text and not text.startswith(("/", "#")):
        return "https://" + text
    return None


def _request_rows(*, dataset: str, config: str, split: str, offset: int, length: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {"dataset": dataset, "config": config, "split": split, "offset": offset, "length": length}
    )
    url = f"{DATASETS_SERVER}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "tiny-browser-agent-webvoyager-runner"})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hugging Face datasets-server request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Hugging Face datasets-server: {exc}") from exc


def _ssl_context() -> ssl.SSLContext:
    """Return an HTTPS context that works in both uv and macOS framework Python.

    Some macOS Python installs do not know the system CA bundle. If certifi is
    available in the active environment, use it; otherwise fall back to the
    interpreter defaults.
    """

    try:
        import certifi  # type: ignore[import-not-found]
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}

    text = value.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return {"raw": text}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


def build_command(args: argparse.Namespace, task: TaskRow) -> list[str]:
    command = ["uv", "run", "main.py", "--planner", "--headless", args.headless]
    if args.grounding:
        command.extend(["--grounding", args.grounding])
    if args.model:
        command.extend(["--model", args.model])
    if args.log_agent:
        command.append("--log")
    if getattr(args, "video_agent", False):
        command.append("--video")
    if args.metadata_initial_url and task.initial_url:
        command.extend(["--initial_url", task.initial_url])
    command.extend(args.extra_arg)
    command.append(task.task)
    return command


def run_task(args: argparse.Namespace, output_dir: Path, task: TaskRow) -> dict[str, Any]:
    command = build_command(args, task)
    started_at = datetime.now().isoformat(timespec="seconds")
    started_monotonic = time.monotonic()
    log_stem = f"{task.index:04d}-{_slugify(task.task_id)}"
    stdout_path = output_dir / f"{log_stem}.stdout.log"
    stderr_path = output_dir / f"{log_stem}.stderr.log"

    record: dict[str, Any] = {
        "row_idx": task.index,
        "id": task.task_id,
        "task": task.task,
        "metadata": task.metadata,
        "command": command,
        "started_at": started_at,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }

    if args.dry_run:
        record.update({"returncode": 0, "status": "dry_run", "duration_seconds": 0.0})
        stdout_path.write_text("DRY RUN: " + _format_command(command) + "\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return record

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        stdout_file.write("$ " + _format_command(command) + "\n\n")
        stdout_file.flush()
        try:
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            returncode = completed.returncode
            status = "passed" if returncode == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            returncode = None
            status = "timeout"
            stderr_file.write(f"\nTimed out after {exc.timeout} seconds.\n")

    record.update(
        {
            "returncode": returncode,
            "status": status,
            "duration_seconds": round(time.monotonic() - started_monotonic, 3),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return record


def run_all(args: argparse.Namespace, tasks: Iterable[TaskRow], output_dir: Path) -> list[dict[str, Any]]:
    task_list = list(tasks)
    summary_path = output_dir / "summary.jsonl"
    results: list[dict[str, Any]] = []

    with summary_path.open("w", encoding="utf-8") as summary_file:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_task, args, output_dir, task): task for task in task_list}
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                try:
                    record = future.result()
                except Exception as exc:  # Keep the batch running when one launcher fails.
                    record = {
                        "row_idx": task.index,
                        "id": task.task_id,
                        "task": task.task,
                        "metadata": task.metadata,
                        "status": "launcher_error",
                        "error": repr(exc),
                    }
                summary_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                summary_file.flush()
                results.append(record)
                print(f"[{record['status']}] row={record['row_idx']} id={record['id']}", flush=True)

    return results


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")
    return slug[:80] or "task"


def _format_command(command: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in command)


def _shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    dataset_log_name = "webvoyager2025valid" if args.dataset == DEFAULT_DATASET else _slugify(args.dataset.replace("/", "-"))
    output_dir = args.output_dir or Path("logs") / dataset_log_name / datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = fetch_tasks(
        dataset=args.dataset,
        config=args.config,
        split=args.split,
        offset=args.offset,
        limit=args.limit,
        task_field=args.task_field,
    )
    if not tasks:
        print("No tasks found.", file=sys.stderr)
        return 1

    print(
        f"Running {len(tasks)} task(s) from {args.dataset}/{args.split} "
        f"with {args.workers} worker(s). Logs: {output_dir}",
        flush=True,
    )
    if args.dry_run:
        for task in tasks:
            print(_format_command(build_command(args, task)))

    results = run_all(args, tasks, output_dir)
    failed = [record for record in results if record.get("status") not in {"passed", "dry_run"}]
    print(f"Done. passed={len(results) - len(failed)} failed={len(failed)} summary={output_dir / 'summary.jsonl'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
