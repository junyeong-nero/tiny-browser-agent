from collections.abc import Callable
from typing import Any

from .playwright import EnvState, PlaywrightBrowser


BrowserAction = Callable[..., EnvState | dict[str, Any]]


def build_browser_action_functions(browser_computer: PlaywrightBrowser) -> list[BrowserAction]:
    def press_key(key: str) -> EnvState:
        """Presses a single keyboard key, such as "Enter", "Escape", "Tab", or "Backspace".

        Use this when a single key needs to be pressed without modifiers. For key
        combinations with modifiers (e.g., "Control+c"), use key_combination instead.

        Args:
            key: The keyboard key to press. Examples: "Enter", "Escape", "Tab",
                "Backspace", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight".
        """
        return browser_computer.key_combination([key])

    def reload_page() -> EnvState:
        """Reloads the current webpage.

        Use this when the page appears stuck, a resource failed to load, or an
        SPA needs to be reset to recover from an error state. This is different
        from go_back/go_forward, which navigate to adjacent entries in history.
        """
        return browser_computer.reload_page()

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

    return [press_key, reload_page, get_accessibility_tree, upload_file]
