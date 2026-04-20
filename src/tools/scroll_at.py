from browser import PlaywrightBrowser, EnvState

from tools.types import denormalize_x, denormalize_y


def handle_scroll_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    direction = args["direction"]
    magnitude = args.get("magnitude", 800)
    if direction in ("up", "down"):
        magnitude = denormalize_y(magnitude, computer)
    elif direction in ("left", "right"):
        magnitude = denormalize_x(magnitude, computer)
    else:
        raise ValueError("Unknown direction: ", direction)

    return computer.scroll_at(
        x=denormalize_x(args["x"], computer),
        y=denormalize_y(args["y"], computer),
        direction=direction,
        magnitude=magnitude,
    )
