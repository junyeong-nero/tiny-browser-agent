import re
from collections import defaultdict
from dataclasses import dataclass

import pydantic


@dataclass(frozen=True)
class NodeInfo:
    role: str
    name: str
    nth: int  # 0-indexed occurrence among identical (role, name) pairs


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


def build_aria_snapshot(raw_yaml: str, url: str) -> AriaSnapshot:
    """Parse Playwright aria_snapshot() YAML and assign sequential integer refs."""
    lines = raw_yaml.splitlines()
    ref_map: dict[int, NodeInfo] = {}
    text_lines: list[str] = []
    occurrence_counter: dict[tuple[str, str], int] = defaultdict(int)
    next_ref = 1

    for line in lines:
        match = _ARIA_LINE_RE.match(line)
        if not match:
            text_lines.append(line)
            continue

        indent = match.group(1)
        role = match.group(2)
        name = match.group(3) or ""
        rest = match.group(4).strip()

        ref = next_ref
        next_ref += 1

        key = (role, name)
        nth = occurrence_counter[key]
        occurrence_counter[key] += 1
        ref_map[ref] = NodeInfo(role=role, name=name, nth=nth)

        name_part = f' "{name}"' if name else ""
        rest_part = f" {rest}" if rest else ""
        text_lines.append(f"{indent}- [{ref}] {role}{name_part}{rest_part}")

    return AriaSnapshot(text="\n".join(text_lines), ref_map=ref_map, url=url)
