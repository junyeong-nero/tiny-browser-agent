from browser import PlaywrightBrowser, EnvState


def handle_wait_5_seconds(computer: PlaywrightBrowser, args: dict) -> EnvState:
    del args
    return computer.wait_5_seconds()
