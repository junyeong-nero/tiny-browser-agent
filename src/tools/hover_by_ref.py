from browser import PlaywrightBrowser, EnvState

from tools.helpers import current_state_after_page_ready, mark_and_resolve_ref_locator


def handle_hover_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = mark_and_resolve_ref_locator(computer, args, "hover_by_ref")
    locator.hover()
    return current_state_after_page_ready(computer)
