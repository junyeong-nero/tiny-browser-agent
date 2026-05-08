"""Descriptor functions for screenshot/coordinate grounding via chat models.

These descriptors expose the same coordinate-based browser controls that
Gemini Computer Use provides, but as regular function declarations for
OpenAI-compatible providers that can accept image inputs.
"""

from typing import Literal

from tools.text_mode_tools import (
    go_back,
    go_forward,
    key_combination,
    navigate,
    open_web_browser,
    wait_5_seconds,
)


def click_at(x: int, y: int) -> dict:
    """Click a point in the current browser screenshot.

    Args:
        x: Horizontal coordinate normalized from 0 (left) to 1000 (right).
        y: Vertical coordinate normalized from 0 (top) to 1000 (bottom).
    """
    ...


def hover_at(x: int, y: int) -> dict:
    """Move the mouse over a point in the current browser screenshot.

    Args:
        x: Horizontal coordinate normalized from 0 (left) to 1000 (right).
        y: Vertical coordinate normalized from 0 (top) to 1000 (bottom).
    """
    ...


def type_text_at(
    x: int,
    y: int,
    text: str,
    press_enter: bool = False,
    clear_before_typing: bool = True,
) -> dict:
    """Click a point and type text there.

    Args:
        x: Horizontal coordinate normalized from 0 (left) to 1000 (right).
        y: Vertical coordinate normalized from 0 (top) to 1000 (bottom).
        text: Text to type.
        press_enter: Whether to press Enter after typing.
        clear_before_typing: Whether to clear existing field contents first.
    """
    ...


def scroll_at(
    x: int,
    y: int,
    direction: Literal["up", "down", "left", "right"] = "down",
    magnitude: int = 800,
) -> dict:
    """Scroll at a point in the current browser screenshot.

    Args:
        x: Horizontal coordinate normalized from 0 (left) to 1000 (right).
        y: Vertical coordinate normalized from 0 (top) to 1000 (bottom).
        direction: Direction to scroll.
        magnitude: Scroll amount normalized to the viewport size.
    """
    ...


def scroll_document(direction: Literal["up", "down"] = "down") -> dict:
    """Scroll the main document.

    Args:
        direction: Direction to scroll.
    """
    ...


def drag_and_drop(x: int, y: int, destination_x: int, destination_y: int) -> dict:
    """Drag from one screenshot point to another.

    Args:
        x: Starting horizontal coordinate normalized from 0 to 1000.
        y: Starting vertical coordinate normalized from 0 to 1000.
        destination_x: Ending horizontal coordinate normalized from 0 to 1000.
        destination_y: Ending vertical coordinate normalized from 0 to 1000.
    """
    ...


VISION_MODE_TOOL_DESCRIPTORS = [
    open_web_browser,
    navigate,
    go_back,
    go_forward,
    key_combination,
    wait_5_seconds,
    click_at,
    hover_at,
    type_text_at,
    scroll_document,
    scroll_at,
    drag_and_drop,
]
