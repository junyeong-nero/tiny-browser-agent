import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pydantic


@dataclass(frozen=True)
class NodeInfo:
    role: str
    name: str
    nth: int  # 0-indexed occurrence among identical (role, name) pairs
    raw_attrs: str = ""
    states: dict[str, str | bool] = field(default_factory=dict)
    actionable: bool = False
    # When set, the node was discovered via DOM augmentation (not ARIA tree),
    # and should be resolved via `[data-tba-dom-ref="<dom_ref>"]` instead of
    # role/name selectors.
    dom_ref: str | None = None


class AriaSnapshot(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    text: str
    ref_map: dict[int, NodeInfo]
    url: str


# Matches ARIA node lines: optional indent + "- " + role + optional '"name"' + optional rest
_ARIA_LINE_RE = re.compile(
    r'^(\s*)-\s+(\w[\w-]*)'
    r'(?:\s+"((?:[^"\\]|\\.)*)")?'
    r'(.*?)$'
)

_ARIA_ATTRS_RE = re.compile(r"\[([^\]]+)\]")
_ACTIONABLE_ROLES = {
    "button",
    "link",
    "checkbox",
    "radio",
    "switch",
    "tab",
    "menuitem",
    "option",
    "combobox",
    "textbox",
    "searchbox",
    "slider",
    "spinbutton",
}
_DISABLED_STATE_NAMES = {"disabled", "aria-disabled"}


def _parse_state_value(raw_value: str | None) -> str | bool:
    if raw_value is None:
        return True
    normalized = raw_value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return raw_value.strip()


def _parse_aria_states(raw_attrs: str) -> dict[str, str | bool]:
    states: dict[str, str | bool] = {}
    for attrs_match in _ARIA_ATTRS_RE.finditer(raw_attrs):
        for token in attrs_match.group(1).split(","):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                key, value = token.split("=", 1)
                states[key.strip()] = _parse_state_value(value)
            else:
                states[token] = True
    return states


def _state_is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "0", "none"}
    return bool(value)


def _is_actionable(role: str, states: dict[str, str | bool]) -> bool:
    if role not in _ACTIONABLE_ROLES:
        return False
    return not any(
        _state_is_truthy(states.get(disabled_state))
        for disabled_state in _DISABLED_STATE_NAMES
    )


def build_aria_snapshot(raw_yaml: str, url: str, ref_offset: int = 0) -> AriaSnapshot:
    """Parse Playwright aria_snapshot() YAML and assign sequential integer refs."""
    lines = raw_yaml.splitlines()
    ref_map: dict[int, NodeInfo] = {}
    text_lines: list[str] = []
    occurrence_counter: dict[tuple[str, str], int] = defaultdict(int)
    next_ref = 1 + ref_offset

    for line in lines:
        match = _ARIA_LINE_RE.match(line)
        if not match:
            text_lines.append(line)
            continue

        indent = match.group(1)
        role = match.group(2)
        name = match.group(3) or ""
        rest = match.group(4).strip()
        states = _parse_aria_states(rest)
        actionable = _is_actionable(role, states)

        ref = next_ref
        next_ref += 1

        key = (role, name)
        nth = occurrence_counter[key]
        occurrence_counter[key] += 1
        ref_map[ref] = NodeInfo(
            role=role,
            name=name,
            nth=nth,
            raw_attrs=rest,
            states=states,
            actionable=actionable,
        )

        name_part = f' "{name}"' if name else ""
        rest_part = f" {rest}" if rest else ""
        actionability_part = "actionable" if actionable else "read-only"
        text_lines.append(
            f"{indent}- [{ref}] {role}{name_part}{rest_part} {actionability_part}"
        )

    return AriaSnapshot(text="\n".join(text_lines), ref_map=ref_map, url=url)
