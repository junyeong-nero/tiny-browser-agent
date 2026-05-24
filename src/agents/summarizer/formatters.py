from __future__ import annotations

from typing import Any, Callable

from google.genai import types


NAVIGATION_ACTION_NAMES = {
    "navigate",
    "search",
    "go_back",
    "go_forward",
    "open_web_browser",
}

ACTION_SUMMARY_TEMPLATES: dict[str, str] = {
    "open_web_browser": "Opened the web browser",
    "observe_page": "Observed the current page",
    "scroll_document": "Scrolled the document {direction}",
    "wait_5_seconds": "Waited for 5 seconds",
    "go_back": "Went back to the previous page",
    "go_forward": "Went forward to the next page",
    "search": "Opened the search page",
}

FALLBACK_REASON_TEMPLATES: dict[str, str] = {
    "navigate": "Needed to open {url}.",
    "click_at": "Needed to click the selected page location.",
    "hover_at": "Needed to inspect the selected page location.",
    "type_text_at": "Needed to enter text into the page.",
    "type_by_ref": "Needed to enter text into the focused field.",
    "click_by_ref": "Needed to click the referenced element.",
    "hover_by_ref": "Needed to inspect the referenced element.",
    "scroll_by_ref": "Needed to scroll the referenced element.",
    "check_by_ref": "Needed to toggle the referenced control.",
    "scroll_document": "Needed to move the page view to continue.",
    "scroll_at": "Needed to move the page view to continue.",
    "wait_5_seconds": "Needed to wait for the page state to settle.",
    "go_back": "Needed to return to the previous page.",
    "go_forward": "Needed to move forward in browser history.",
    "search": "Needed to open the search page.",
    "key_combination": "Needed to trigger a keyboard shortcut.",
    "drag_and_drop": "Needed to move an on-page element.",
}

PHASE_GROUPS: dict[str, tuple[str, str]] = {
    "open_web_browser": ("phase-navigation", "페이지 이동"),
    "observe_page": ("phase-observation", "페이지 확인"),
    "search": ("phase-navigation", "페이지 이동"),
    "navigate": ("phase-navigation", "페이지 이동"),
    "go_back": ("phase-navigation", "페이지 이동"),
    "go_forward": ("phase-navigation", "페이지 이동"),
    "click_at": ("phase-interaction", "페이지 상호작용"),
    "hover_at": ("phase-interaction", "페이지 상호작용"),
    "type_text_at": ("phase-input", "입력 및 조작"),
    "key_combination": ("phase-input", "입력 및 조작"),
    "drag_and_drop": ("phase-input", "입력 및 조작"),
}

DEFAULT_PHASE = ("phase-observation", "페이지 확인")


class _MissingArgs(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        return None


def _format_action_template(template: str, action_args: dict[str, Any]) -> str:
    return template.format_map(_MissingArgs(action_args))


def _format_point_action(label: str, action_args: dict[str, Any]) -> str:
    return f"{label} at ({action_args.get('x')}, {action_args.get('y')})"


def _format_scroll_at(action_args: dict[str, Any]) -> str:
    return (
        f"Scrolled {action_args.get('direction')} at "
        f"({action_args.get('x')}, {action_args.get('y')})"
    )


def _format_drag_and_drop(action_args: dict[str, Any]) -> str:
    return (
        f"Dragged from ({action_args.get('x')}, {action_args.get('y')}) to "
        f"({action_args.get('destination_x')}, {action_args.get('destination_y')})"
    )


def _format_type_text_at(action_args: dict[str, Any]) -> str:
    text = action_args.get("text")
    location = f"({action_args.get('x')}, {action_args.get('y')})"
    if text:
        suffix = " and pressed Enter" if action_args.get("press_enter") else ""
        return f'Typed "{text}" at {location}{suffix}'
    return _format_point_action("Typed text", action_args)


def _format_type_by_ref(action_args: dict[str, Any]) -> str:
    text = action_args.get("text")
    ref = action_args.get("ref")
    suffix = " and pressed Enter" if action_args.get("press_enter") else ""
    if text:
        return f'Typed "{text}" into ref {ref}{suffix}'
    return f"Typed text into ref {ref}{suffix}"


ACTION_SUMMARY_FORMATTERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "click_at": lambda args: _format_point_action("Clicked", args),
    "hover_at": lambda args: _format_point_action("Hovered", args),
    "type_text_at": _format_type_text_at,
    "scroll_at": _format_scroll_at,
    "navigate": lambda args: f"Navigated to {args.get('url')}",
    "key_combination": lambda args: f"Pressed key combination {args.get('keys')}",
    "drag_and_drop": _format_drag_and_drop,
    "click_by_ref": lambda args: f"Clicked ref {args.get('ref')}",
    "hover_by_ref": lambda args: f"Hovered ref {args.get('ref')}",
    "type_by_ref": _format_type_by_ref,
    "scroll_by_ref": lambda args: f"Scrolled {args.get('direction')} on ref {args.get('ref')}",
    "check_by_ref": lambda args: f"Toggled ref {args.get('ref')}",
}


def build_action_summary(function_call: types.FunctionCall) -> str:
    action_name = function_call.name or "action"
    action_args = dict(function_call.args or {})

    formatter = ACTION_SUMMARY_FORMATTERS.get(action_name)
    if formatter is not None:
        return formatter(action_args)

    template = ACTION_SUMMARY_TEMPLATES.get(action_name)
    if template is not None:
        return _format_action_template(template, action_args)

    return f"Executed {action_name}"


def build_fallback_reason(function_call: types.FunctionCall) -> str:
    action_name = function_call.name or "action"
    action_args = dict(function_call.args or {})
    template = FALLBACK_REASON_TEMPLATES.get(action_name)
    if template is not None:
        return _format_action_template(template, action_args)
    return f"Needed to execute {action_name}."

