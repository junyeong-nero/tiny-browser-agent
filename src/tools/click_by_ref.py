from typing import Any

from browser import PlaywrightBrowser, EnvState
from browser.aria_snapshot import NodeInfo

from tools.helpers import (
    click_locator,
    current_state_after_page_ready,
    mark_and_resolve_ref_locator,
    resolve_ref_node,
)


def _not_actionable_response(
    *,
    ref: int,
    node: NodeInfo | None,
    error_type: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "not_actionable",
        "tool_name": "click_by_ref",
        "error_type": error_type,
        "error": (
            f"{reason} Choose an actionable ref such as a button, link, tab, "
            "checkbox, textbox, or explain that the requested state is already complete."
        ),
        "ref": ref,
        "role": node.role if node is not None else None,
        "name": node.name if node is not None else None,
    }


def _is_locator_visible(locator) -> bool:
    try:
        return bool(locator.is_visible())
    except Exception:
        return True


def _is_locator_enabled(locator) -> bool:
    try:
        return bool(locator.is_enabled())
    except Exception:
        return True


def handle_click_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState | dict[str, Any]:
    locator = mark_and_resolve_ref_locator(computer, args, "click_by_ref")
    node = resolve_ref_node(computer, args)
    ref = int(args["ref"])
    if node is not None and not node.actionable:
        return _not_actionable_response(
            ref=ref,
            node=node,
            error_type="NotActionable",
            reason=f"Ref {ref} has role {node.role!r}, which is not currently actionable.",
        )
    if not _is_locator_visible(locator):
        return _not_actionable_response(
            ref=ref,
            node=node,
            error_type="NotVisible",
            reason=f"Ref {ref} is not visible.",
        )
    if not _is_locator_enabled(locator):
        return _not_actionable_response(
            ref=ref,
            node=node,
            error_type="NotEnabled",
            reason=f"Ref {ref} is not enabled.",
        )
    computer.highlight_locator(locator, kind="click")
    click_locator(locator, node=node)
    return current_state_after_page_ready(computer)
