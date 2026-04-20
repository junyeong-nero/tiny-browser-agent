from browser import PlaywrightBrowser, EnvState


def handle_search(computer: PlaywrightBrowser, args: dict) -> EnvState:
    del args
    return computer.search()
