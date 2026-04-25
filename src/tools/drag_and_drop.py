from browser import PlaywrightBrowser, EnvState

from tools.helpers import denormalized_point


def handle_drag_and_drop(computer: PlaywrightBrowser, args: dict) -> EnvState:
    x, y = denormalized_point(args, computer)
    destination_x, destination_y = denormalized_point(
        {"x": args["destination_x"], "y": args["destination_y"]},
        computer,
    )
    return computer.drag_and_drop(
        x=x,
        y=y,
        destination_x=destination_x,
        destination_y=destination_y,
    )
