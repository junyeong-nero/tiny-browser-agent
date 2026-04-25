from typing import Literal

from browser import PlaywrightBrowser

from tools.types import denormalize_x, denormalize_y


def denormalized_point(args: dict, computer: PlaywrightBrowser) -> tuple[int, int]:
    return denormalize_x(args["x"], computer), denormalize_y(args["y"], computer)


def denormalized_scroll_magnitude(
    direction: Literal["up", "down", "left", "right"],
    magnitude: int,
    computer: PlaywrightBrowser,
) -> int:
    if direction in ("up", "down"):
        return denormalize_y(magnitude, computer)
    if direction in ("left", "right"):
        return denormalize_x(magnitude, computer)
    raise ValueError("Unknown direction: ", direction)


def resolve_ref_locator(computer: PlaywrightBrowser, args: dict):
    return computer.resolve_ref(int(args["ref"]))
