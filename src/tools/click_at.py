from browser import PlaywrightBrowser, EnvState

from tools.helpers import denormalized_point


def handle_click_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    x, y = denormalized_point(args, computer)
    return computer.click_at(x=x, y=y)
