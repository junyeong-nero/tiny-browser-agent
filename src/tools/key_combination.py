from browser import PlaywrightBrowser, EnvState


def handle_key_combination(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.key_combination(args["keys"].split("+"))
