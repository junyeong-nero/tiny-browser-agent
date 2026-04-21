"""
Descriptor functions for text/mixed grounding mode.

These are used ONLY for building LLM function declarations via
build_function_declaration(). Actual execution is handled by the
BrowserToolExecutor handler map.
"""
from typing import Literal


def navigate(url: str) -> dict:
    """Navigate the browser to a URL.

    Args:
        url: The full URL to navigate to (include https:// prefix when known).
    """
    ...


def go_back() -> dict:
    """Navigate back to the previous page in browser history."""
    ...


def go_forward() -> dict:
    """Navigate forward to the next page in browser history."""
    ...


def search() -> dict:
    """Navigate to the default search engine homepage."""
    ...


def key_combination(keys: list[str]) -> dict:
    """Press a keyboard shortcut combination (e.g. Ctrl+C, Enter).

    Args:
        keys: List of key names to press together, e.g. ["Control", "A"].
    """
    ...


def wait_5_seconds() -> dict:
    """Wait 5 seconds for a page or animation to settle."""
    ...


def click_by_ref(ref: int) -> dict:
    """Click an element identified by its ARIA snapshot reference number.

    Args:
        ref: The integer ref shown in brackets in the ARIA snapshot, e.g. [5].
    """
    ...


def type_by_ref(ref: int, text: str, press_enter: bool = False) -> dict:
    """Type text into an element identified by its ARIA snapshot reference number.

    Args:
        ref: The integer ref shown in brackets in the ARIA snapshot.
        text: The text to type into the element.
        press_enter: If True, press Enter after typing.
    """
    ...


def hover_by_ref(ref: int) -> dict:
    """Hover the mouse over an element by its ARIA snapshot reference number.

    Args:
        ref: The integer ref shown in brackets in the ARIA snapshot.
    """
    ...


def scroll_by_ref(ref: int, direction: Literal["up", "down"] = "down") -> dict:
    """Scroll relative to an element by its ARIA snapshot reference number.

    Args:
        ref: The integer ref shown in brackets in the ARIA snapshot.
        direction: Scroll direction — "up" or "down".
    """
    ...


# Descriptors exposed for text/mixed mode
TEXT_MODE_TOOL_DESCRIPTORS = [
    navigate,
    go_back,
    go_forward,
    search,
    key_combination,
    wait_5_seconds,
    click_by_ref,
    type_by_ref,
    hover_by_ref,
    scroll_by_ref,
]
