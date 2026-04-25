from browser import PlaywrightBrowser, EnvState

from tools.helpers import resolve_ref_locator


def handle_hover_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = resolve_ref_locator(computer, args)
    locator.hover()
    computer._page.wait_for_load_state()
    return computer.current_state()
