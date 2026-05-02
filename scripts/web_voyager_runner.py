#!/usr/bin/env python3
"""Run WebVoyager2025Valid tasks through the local browser agent in parallel.

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
DATASETS_SERVER = "https://datasets-server.huggingface.co/rows"
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class TaskRow:
    index: int
    task: str
    metadata: dict[str, Any]

    @property
    def task_id(self) -> str:
        raw_id = self.metadata.get("id") if isinstance(self.metadata, dict) else None
        return str(raw_id or f"row-{self.index}")

    @property
    def initial_url(self) -> str | None:
        raw_url = self.metadata.get("web") if isinstance(self.metadata, dict) else None
        if isinstance(raw_url, str) and raw_url.startswith(("http://", "https://")):
            return raw_url
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load tasks from convergence-ai/WebVoyager2025Valid on Hugging Face "
            "and run `uv run main.py --planner <task>` in parallel."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Hugging Face dataset name.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Dataset config name.")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Dataset split name.")
    parser.add_argument("--offset", type=int, default=0, help="First dataset row offset to run.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of tasks to run.")
    parser.add_argument("--workers", type=int, default=2, help="Number of parallel subprocesses.")
    parser.add_argument("--task-field", default="task", help="Dataset column containing the query text.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for per-task logs and summary.jsonl. Defaults to logs/webvoyager2025valid/<timestamp>.",
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
        help="Forward --log to main.py so each browser-agent run records Playwright artifacts.",
    )
    parser.add_argument(
        "--metadata-initial-url",
        action="store_true",
        help="Forward metadata['web'] as --initial_url when present.",
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
    return parser.parse_args(argv)


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
            task = row.get(task_field)
            if not isinstance(task, str) or not task.strip():
                raise ValueError(f"Row {row_index} does not contain a non-empty {task_field!r} field: {row!r}")
            rows.append(TaskRow(index=row_index, task=task.strip(), metadata=_parse_metadata(row.get("metadata"))))

        fetched = len(page_rows)
        if fetched < page_size:
            break
        next_offset += fetched
        remaining -= fetched

    return rows


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

    output_dir = args.output_dir or Path("logs") / "webvoyager2025valid" / datetime.now().strftime("%Y%m%d-%H%M%S")
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
