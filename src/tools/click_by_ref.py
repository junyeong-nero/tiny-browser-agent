from browser import PlaywrightBrowser, EnvState

from tools.helpers import (
    click_locator,
    current_state_after_page_ready,
    mark_and_resolve_ref_locator,
    resolve_ref_node,
)


def handle_click_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = mark_and_resolve_ref_locator(computer, args, "click_by_ref")
    node = resolve_ref_node(computer, args)
    click_locator(locator, node=node)
    return current_state_after_page_ready(computer)
