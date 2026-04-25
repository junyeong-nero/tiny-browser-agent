from browser import PlaywrightBrowser, EnvState

from tools.helpers import denormalized_point, denormalized_scroll_magnitude


def handle_scroll_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    direction = args["direction"]
    magnitude = denormalized_scroll_magnitude(
        direction,
        args.get("magnitude", 800),
        computer,
    )
    x, y = denormalized_point(args, computer)

    return computer.scroll_at(
        x=x,
        y=y,
        direction=direction,
        magnitude=magnitude,
    )
