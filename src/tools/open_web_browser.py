from browser import PlaywrightBrowser, EnvState


def handle_open_web_browser(computer: PlaywrightBrowser, args: dict) -> EnvState:
    del args
    return computer.open_web_browser()
