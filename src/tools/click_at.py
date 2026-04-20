from browser import PlaywrightBrowser, EnvState

from tools.types import denormalize_x, denormalize_y


def handle_click_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.click_at(
        x=denormalize_x(args["x"], computer),
        y=denormalize_y(args["y"], computer),
    )
