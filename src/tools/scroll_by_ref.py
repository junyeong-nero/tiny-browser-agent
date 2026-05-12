from typing import Literal

from browser import PlaywrightBrowser, EnvState
from browser.playwright import PlaywrightError, PlaywrightTimeoutError

from tools.helpers import resolve_ref_locator

SCROLL_REF_TIMEOUT_MS = 3_000


def handle_scroll_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    direction: Literal["up", "down"] = args.get("direction", "down")

    locator = resolve_ref_locator(computer, args)
    try:
        locator.scroll_into_view_if_needed(timeout=SCROLL_REF_TIMEOUT_MS)
        bounding_box = locator.bounding_box()
    except (PlaywrightTimeoutError, PlaywrightError):
        return computer.scroll_document(direction)

    if bounding_box:
        cx = int(bounding_box["x"] + bounding_box["width"] / 2)
        cy = int(bounding_box["y"] + bounding_box["height"] / 2)
        return computer.scroll_at(cx, cy, direction)

    return computer.scroll_document(direction)
