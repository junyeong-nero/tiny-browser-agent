from typing import Any, Literal

from browser.aria_snapshot import NodeInfo

from browser import PlaywrightBrowser
from browser.playwright import PlaywrightError, PlaywrightTimeoutError

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


def mark_and_resolve_ref_locator(
    computer: PlaywrightBrowser,
    args: dict[str, Any],
    action_name: str,
):
    computer._mark_last_action(action_name)
    return resolve_ref_locator(computer, args)


def wait_for_page_ready(computer: PlaywrightBrowser) -> None:
    computer._page.wait_for_load_state()


def current_state_after_page_ready(computer: PlaywrightBrowser):
    wait_for_page_ready(computer)
    return computer.current_state()


def resolve_ref_node(computer: PlaywrightBrowser, args: dict) -> NodeInfo | None:
    """Return cached ARIA node metadata when available.

    ``resolve_ref`` remains the source of truth for stale-ref validation; this
    helper is intentionally best-effort so tests and non-Playwright browser
    doubles do not need to expose a full ARIA cache.
    """
    ref_map = getattr(computer, "_aria_ref_map", None)
    if not ref_map:
        return None
    return ref_map.get(int(args["ref"]))


def click_locator(locator, node: NodeInfo | None = None) -> None:
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
        if _is_pointer_interception_error(exc):
            locator.click(force=True, timeout=CLICK_TIMEOUT_MS)
            return
        if _is_hidden_select_option_error(exc, node):
            _select_option_locator(locator)
            return
        raise


def _is_pointer_interception_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "intercepts pointer events" in message


def _is_hidden_select_option_error(exc: Exception, node: NodeInfo | None) -> bool:
    """Detect the Playwright failure raised when clicking a native <option>."""
    if node is None or node.role != "option":
        return False
    message = str(exc).lower()
    return "element is not visible" in message or "not visible" in message


def _select_option_locator(locator) -> None:
    """Select a resolved <option> without requiring the option popup to be visible.

    Native ``<option>`` elements are not independently visible/clickable in
    Chromium; selecting them requires mutating the owning ``<select>`` and
    dispatching the same events that application code listens for.
    """
    selected = locator.evaluate(
        """
        (option) => {
            if (!(option instanceof HTMLOptionElement)) return false;
            const select = option.closest('select');
            if (!select) return false;
            select.value = option.value;
            option.selected = true;
            select.dispatchEvent(new Event('input', { bubbles: true }));
            select.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        """
    )
    if not selected:
        raise RuntimeError("resolved option ref is not inside a selectable <select>")
