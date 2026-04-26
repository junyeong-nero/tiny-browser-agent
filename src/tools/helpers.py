from typing import Literal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from browser import PlaywrightBrowser

from tools.types import denormalize_x, denormalize_y


CLICK_TIMEOUT_MS = 5_000


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


def click_locator(locator) -> None:
    """Click a locator, falling back when Playwright's hit target is overlaid.

    Some responsive navigation bars render both a semantic button and a link in
    the same list item. Playwright can resolve the intended ARIA node but refuse
    the click because the sibling/child link intercepts pointer events. In that
    case, retry with ``force=True`` so the click is dispatched to the resolved
    locator instead of waiting for the page layout to change for 30 seconds.
    """
    try:
        locator.click(timeout=CLICK_TIMEOUT_MS)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        if not _is_pointer_interception_error(exc):
            raise
        locator.click(force=True, timeout=CLICK_TIMEOUT_MS)


def _is_pointer_interception_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "intercepts pointer events" in message
