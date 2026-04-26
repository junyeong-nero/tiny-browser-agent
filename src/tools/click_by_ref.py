from browser import PlaywrightBrowser, EnvState

from tools.helpers import click_locator, resolve_ref_locator


def handle_click_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    computer._mark_last_action("click_by_ref")
    locator = resolve_ref_locator(computer, args)
    click_locator(locator)
    computer._page.wait_for_load_state()
    return computer.current_state()
