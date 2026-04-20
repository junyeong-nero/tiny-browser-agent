from browser import PlaywrightBrowser, EnvState


def handle_scroll_document(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.scroll_document(args["direction"])
