from browser import PlaywrightBrowser, EnvState


def handle_go_back(computer: PlaywrightBrowser, args: dict) -> EnvState:
    del args
    return computer.go_back()
