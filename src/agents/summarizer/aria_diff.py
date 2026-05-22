from __future__ import annotations


_TRUNCATION_NOTE = "\n… (truncated)"


def compute_aria_diff(
    previous_snapshot: str | None,
    current_snapshot: str | None,
    *,
    max_chars: int = 2000,
) -> str | None:
    """Return a compact line-level diff between two ARIA snapshots.

    Output format:
      header line + sequence of `+ <line>` / `- <line>` markers.
    Returns None when both snapshots are empty or identical.
    """
    if not current_snapshot:
        return None

    if not previous_snapshot:
        body = "\n".join(f"+ {line}" for line in current_snapshot.splitlines() if line.strip())
        if not body:
            return None
        rendered = f"[initial snapshot]\n{body}"
        return _truncate(rendered, max_chars)

    if previous_snapshot == current_snapshot:
        return None

    previous_lines = {line for line in previous_snapshot.splitlines() if line.strip()}
    current_lines = {line for line in current_snapshot.splitlines() if line.strip()}

    added = [line for line in current_snapshot.splitlines() if line in (current_lines - previous_lines)]
    removed = [line for line in previous_snapshot.splitlines() if line in (previous_lines - current_lines)]

    if not added and not removed:
        return None

    parts: list[str] = ["[aria diff]"]
    parts.extend(f"+ {line}" for line in added)
    parts.extend(f"- {line}" for line in removed)

    return _truncate("\n".join(parts), max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len(_TRUNCATION_NOTE))
    return text[:keep] + _TRUNCATION_NOTE
