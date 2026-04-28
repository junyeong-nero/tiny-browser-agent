import os


def require_env(name: str, missing_message: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(missing_message)
    return value


def optional_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    if stripped or default is None:
        return stripped
    return default


def parse_timeout_seconds() -> float:
    timeout_value = os.environ.get("ACTION_SUMMARY_TIMEOUT_SECONDS", "15")
    try:
        return float(timeout_value)
    except ValueError as exc:
        raise ValueError("ACTION_SUMMARY_TIMEOUT_SECONDS must be a number.") from exc
