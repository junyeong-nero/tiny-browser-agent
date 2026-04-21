from browser import PlaywrightBrowser, EnvState


def handle_click_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    ref = int(args["ref"])
    locator = computer.resolve_ref(ref)
    locator.click()
    computer._page.wait_for_load_state()
    return computer.current_state()
