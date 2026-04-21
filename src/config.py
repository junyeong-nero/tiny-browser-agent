from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


_config: dict[str, Any] | None = None


def _get() -> dict[str, Any]:
    global _config
    if _config is None:
        _config = _load()
    return _config


def actor_model() -> str:
    return _get()["models"]["actor"]


def planner_model() -> str:
    return _get()["models"]["planner"]


def summary_model() -> str:
    return _get()["models"]["summary"]
