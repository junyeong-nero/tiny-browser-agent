"""Run browser-agent tasks from a Hugging Face datasets-server split."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DATASETS_SERVER_ROWS_URL = "https://datasets-server.huggingface.co/rows"
MAX_PAGE_SIZE = 100
AUTO_TASK_FIELDS = ("task", "prompt", "question", "instruction")


@dataclass(frozen=True)
class TaskRow:
    index: int
    task: str
    metadata: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    initial_url: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="convergence-ai/WebVoyager2025Valid")
    parser.add_argument("--config", default="default")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--task-field", default="auto")
    parser.add_argument("--level", action="append", default=[])
    parser.add_argument("--headless", default="True")
    parser.add_argument("--grounding")
    parser.add_argument("--model")
    parser.add_argument("--log-agent", action="store_true")
    parser.add_argument("--video-agent", action="store_true")
    parser.add_argument("--metadata-initial-url", action="store_true", default=True)
    parser.add_argument("--extra-arg", action="append", default=[])

    args = parser.parse_args(argv)
    if args.dataset == "junyeong-nero/korean-online-mind2web":
        args.config = "default"
        args.split = "train"
        if args.task_field == "auto":
            args.task_field = "task"
    return args


def _request_rows(
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int,
    length: int,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "dataset": dataset,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    with urllib.request.urlopen(f"{DATASETS_SERVER_ROWS_URL}?{query}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {"metadata": metadata}
    if not isinstance(metadata, dict):
        metadata = {}
    merged = dict(metadata)
    for key, value in row.items():
        if key != "metadata":
            merged.setdefault(key, value)
    return merged


def _task_text(row: dict[str, Any], task_field: str) -> str:
    if task_field != "auto":
        value = row.get(task_field)
        return "" if value is None else str(value)
    for field_name in AUTO_TASK_FIELDS:
        value = row.get(field_name)
        if value:
            return str(value)
    return ""


def _initial_url(row: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    for key in ("url", "website", "web", "initial_url"):
        value = row.get(key) or metadata.get(key)
        if value:
            return str(value)
    return None


def _matches_levels(metadata: dict[str, Any], levels: list[str] | None) -> bool:
    if not levels:
        return True
    wanted = {level.lower() for level in levels}
    return str(metadata.get("level", "")).lower() in wanted


def fetch_tasks(
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int,
    limit: int,
    task_field: str,
    levels: list[str] | None = None,
) -> list[TaskRow]:
    tasks: list[TaskRow] = []
    cursor = offset
    while len(tasks) < limit:
        page = _request_rows(
            dataset=dataset,
            config=config,
            split=split,
            offset=cursor,
            length=min(MAX_PAGE_SIZE, max(1, limit - len(tasks))),
        )
        rows = page.get("rows") or []
        if not rows:
            break
        for item in rows:
            row = item.get("row") or {}
            metadata = _parse_metadata(row)
            if not _matches_levels(metadata, levels):
                continue
            index = int(item.get("row_idx", cursor))
            task = _task_text(row, task_field)
            if not task:
                continue
            task_id = str(row.get("task_id") or row.get("id") or index)
            tasks.append(
                TaskRow(
                    index=index,
                    task=task,
                    metadata=metadata,
                    task_id=task_id,
                    initial_url=_initial_url(row, metadata),
                )
            )
            if len(tasks) >= limit:
                break
        cursor += len(rows)
        if len(rows) < min(MAX_PAGE_SIZE, max(1, limit)):
            break
    return tasks


def _normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def build_command(args: argparse.Namespace, task: TaskRow) -> list[str]:
    command = ["uv", "run", "main.py", "--planner", "--headless", args.headless]
    if args.grounding:
        command.extend(["--grounding", args.grounding])
    if args.model:
        command.extend(["--model", args.model])
    if args.log_agent:
        command.append("--log")
    if args.video_agent:
        command.append("--video")
    if args.metadata_initial_url:
        initial_url = _normalize_url(
            task.initial_url
            or str(task.metadata.get("url") or task.metadata.get("website") or "")
        )
        if initial_url:
            command.extend(["--initial_url", initial_url])
    for extra_arg in args.extra_arg:
        command.append(extra_arg)
    command.append(task.task)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tasks = fetch_tasks(
        dataset=args.dataset,
        config=args.config,
        split=args.split,
        offset=args.offset,
        limit=args.limit,
        task_field=args.task_field,
        levels=args.level,
    )
    failures = 0
    for task in tasks:
        completed = subprocess.run(build_command(args, task), check=False)
        if completed.returncode != 0:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
