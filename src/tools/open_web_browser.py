from browser import PlaywrightBrowser, EnvState


def handle_open_web_browser(computer: PlaywrightBrowser, args: dict) -> EnvState:
    url = args.get("url")
    if url:
        return computer.navigate(url)
    return computer.open_web_browser()
