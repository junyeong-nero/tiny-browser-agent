from collections.abc import Callable, Iterable
from typing import Any, Literal

from .playwright import EnvState, PlaywrightBrowser


BrowserAction = Callable[..., EnvState | dict[str, Any]]
BrowserActionName = Literal[
    "reload_page",
    "list_tabs",
    "switch_to_next_tab",
    "switch_to_previous_tab",
    "switch_to_tab",
    "close_current_tab",
    "get_accessibility_tree",
    "upload_file",
]
DEFAULT_BROWSER_ACTIONS: tuple[BrowserActionName, ...] = (
    "reload_page",
    "list_tabs",
    "switch_to_next_tab",
    "switch_to_previous_tab",
    "switch_to_tab",
    "close_current_tab",
)


def build_browser_action_functions(
    browser_computer: PlaywrightBrowser,
    *,
    include: Iterable[BrowserActionName] = DEFAULT_BROWSER_ACTIONS,
) -> list[BrowserAction]:
    def reload_page() -> EnvState:
        """Reloads the current webpage.

        Use this when the page appears stuck, a resource failed to load, or an
        SPA needs to be reset to recover from an error state. This is different
        from go_back/go_forward, which navigate to adjacent entries in history.
        """
        return browser_computer.reload_page()

    def list_tabs() -> dict[str, Any]:
        """Lists open browser tabs with their indexes, URLs, titles, and active status.

        Use this when an action may have opened a new tab or popup, or when
        go_back does not change the URL/page and you need to identify the
        original tab before switching or closing the current tab.
        """
        return browser_computer.list_tabs()

    def switch_to_next_tab() -> EnvState:
        """Switches focus to the next open browser tab.

        Use this when an action opened a new tab or when the needed content is in
        another existing tab.
        """
        return browser_computer.switch_to_next_tab()

    def switch_to_previous_tab() -> EnvState:
        """Switches focus to the previous open browser tab.

        Use this when you need to return to the prior tab in the current browser
        window.
        """
        return browser_computer.switch_to_previous_tab()

    def switch_to_tab(index: int) -> EnvState:
        """Switches focus to the open browser tab at the given zero-based index.

        Args:
            index: Zero-based tab index from list_tabs.
        """
        return browser_computer.switch_to_tab(index=index)

    def close_current_tab() -> EnvState:
        """Closes the current browser tab and focuses another open tab.

        Use this to return from a newly opened tab or popup to the original tab;
        do not repeatedly use go_back for that case. Closing a tab is different
        from browser history navigation.
        """
        return browser_computer.close_current_tab()

    def get_accessibility_tree() -> dict[str, Any]:
        """Returns a serialized accessibility tree for the current webpage.

        Use this to disambiguate visually similar elements, inspect non-visible
        text (e.g., aria-labels), or confirm structure before clicking. The
        response does not include a screenshot; take another action or call
        open_web_browser if you need visual confirmation afterwards.
        """
        return browser_computer.get_accessibility_tree()

    def upload_file(x: int, y: int, path: str) -> EnvState:
        """Uploads a local file to a file input element at the given coordinate.

        Use this when a page has an <input type="file"> that cannot be opened
        by a normal click.

        Args:
            x: Horizontal coordinate of the file input (0-1000 normalized).
            y: Vertical coordinate of the file input (0-1000 normalized).
            path: Absolute path to a local file that exists under an allowed
                upload root (current working directory or system temp by default).
        """
        width, height = browser_computer.screen_size()
        absolute_x = int(x / 1000 * width)
        absolute_y = int(y / 1000 * height)
        return browser_computer.upload_file(x=absolute_x, y=absolute_y, path=path)

    action_functions: dict[BrowserActionName, BrowserAction] = {
        "reload_page": reload_page,
        "list_tabs": list_tabs,
        "switch_to_next_tab": switch_to_next_tab,
        "switch_to_previous_tab": switch_to_previous_tab,
        "switch_to_tab": switch_to_tab,
        "close_current_tab": close_current_tab,
        "get_accessibility_tree": get_accessibility_tree,
        "upload_file": upload_file,
    }
    include_set = set(include)
    return [
        action
        for name, action in action_functions.items()
        if name in include_set
    ]
