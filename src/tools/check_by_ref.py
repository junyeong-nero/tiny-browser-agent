from typing import Any

from browser import PlaywrightBrowser

from tools.helpers import resolve_ref_locator, resolve_ref_node


def _best_effort_value(locator) -> str | None:
    try:
        return locator.input_value()
    except Exception:
        return None


def handle_check_by_ref(computer: PlaywrightBrowser, args: dict) -> dict[str, Any]:
    locator = resolve_ref_locator(computer, args)
    node = resolve_ref_node(computer, args)
    return {
        "ref": int(args["ref"]),
        "role": node.role if node is not None else None,
        "name": node.name if node is not None else None,
        "visible": locator.is_visible(),
        "enabled": locator.is_enabled(),
        "text": locator.text_content(),
        "value": _best_effort_value(locator),
    }
