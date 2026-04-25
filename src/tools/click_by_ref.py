from browser import PlaywrightBrowser, EnvState

from tools.helpers import resolve_ref_locator


def handle_click_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = resolve_ref_locator(computer, args)
    locator.click()
    computer._page.wait_for_load_state()
    return computer.current_state()
