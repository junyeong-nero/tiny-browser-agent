from typing import Literal

from browser import PlaywrightBrowser, EnvState

from tools.helpers import resolve_ref_locator


def handle_scroll_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    direction: Literal["up", "down"] = args.get("direction", "down")

    locator = resolve_ref_locator(computer, args)
    locator.scroll_into_view_if_needed()

    bounding_box = locator.bounding_box()
    if bounding_box:
        cx = int(bounding_box["x"] + bounding_box["width"] / 2)
        cy = int(bounding_box["y"] + bounding_box["height"] / 2)
        return computer.scroll_at(cx, cy, direction)

    return computer.scroll_document(direction)
