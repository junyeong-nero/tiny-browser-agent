from browser import PlaywrightBrowser, EnvState

from tools.types import denormalize_x, denormalize_y


def handle_drag_and_drop(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.drag_and_drop(
        x=denormalize_x(args["x"], computer),
        y=denormalize_y(args["y"], computer),
        destination_x=denormalize_x(args["destination_x"], computer),
        destination_y=denormalize_y(args["destination_y"], computer),
    )
