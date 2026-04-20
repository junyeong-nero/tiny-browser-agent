from browser import PlaywrightBrowser, EnvState


def handle_navigate(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.navigate(args["url"])
