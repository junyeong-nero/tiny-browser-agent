from collections.abc import Callable
from typing import Any

from google.genai import types

from browser import PlaywrightBrowser
from tools.click_at import handle_click_at
from tools.constants import PREDEFINED_COMPUTER_USE_FUNCTIONS
from tools.drag_and_drop import handle_drag_and_drop
from tools.go_back import handle_go_back
from tools.go_forward import handle_go_forward
from tools.hover_at import handle_hover_at
from tools.key_combination import handle_key_combination
from tools.navigate import handle_navigate
from tools.open_web_browser import handle_open_web_browser
from tools.scroll_at import handle_scroll_at
from tools.scroll_document import handle_scroll_document
from tools.search import handle_search
from tools.type_text_at import handle_type_text_at
from tools.types import (
    CustomFunction,
    ExecutedCall,
    ToolBatchResult,
    ToolResult,
    is_env_state_result,
)
from tools.wait_5_seconds import handle_wait_5_seconds


class BrowserToolExecutor:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        custom_functions: list[CustomFunction] | None = None,
    ) -> None:
        self._browser_computer = browser_computer
        self._custom_functions = {
            custom_function.__name__: custom_function
            for custom_function in (custom_functions or [])
        }
        self._handlers: dict[str, Callable[[dict], ToolResult]] = {
            "open_web_browser": lambda args: handle_open_web_browser(browser_computer, args),
            "click_at": lambda args: handle_click_at(browser_computer, args),
            "hover_at": lambda args: handle_hover_at(browser_computer, args),
            "type_text_at": lambda args: handle_type_text_at(browser_computer, args),
            "scroll_document": lambda args: handle_scroll_document(browser_computer, args),
            "scroll_at": lambda args: handle_scroll_at(browser_computer, args),
            "wait_5_seconds": lambda args: handle_wait_5_seconds(browser_computer, args),
            "go_back": lambda args: handle_go_back(browser_computer, args),
            "go_forward": lambda args: handle_go_forward(browser_computer, args),
            "search": lambda args: handle_search(browser_computer, args),
            "navigate": lambda args: handle_navigate(browser_computer, args),
            "key_combination": lambda args: handle_key_combination(browser_computer, args),
            "drag_and_drop": lambda args: handle_drag_and_drop(browser_computer, args),
        }

    def build_tools(
        self,
        build_function_declaration: Callable[[Callable[..., object]], types.FunctionDeclaration],
        excluded_predefined_functions: list[str] | None = None,
    ) -> list[types.Tool]:
        custom_function_declarations = [
            build_function_declaration(custom_function)
            for custom_function in self._custom_functions.values()
        ]
        return [
            types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER,
                    excluded_predefined_functions=excluded_predefined_functions or [],
                )
            ),
            types.Tool(function_declarations=custom_function_declarations),
        ]

    def execute_call(self, action: types.FunctionCall) -> ExecutedCall:
        result = self.execute(action)
        artifacts = None
        if is_env_state_result(result):
            artifacts = self._latest_artifact_metadata()
        return ExecutedCall(function_call=action, result=result, artifacts=artifacts)

    def serialize_function_response(
        self,
        executed_call: ExecutedCall,
        extra_response_fields: dict[str, Any] | None = None,
    ) -> types.FunctionResponse:
        response_fields = dict(extra_response_fields or {})
        if is_env_state_result(executed_call.result):
            return types.FunctionResponse(
                name=executed_call.function_call.name,
                response={
                    "url": executed_call.result.url,
                    **response_fields,
                },
                parts=[
                    types.FunctionResponsePart(
                        inline_data=types.FunctionResponseBlob(
                            mime_type="image/png",
                            data=executed_call.result.screenshot,
                        )
                    )
                ],
            )

        dict_result = executed_call.result
        if not isinstance(dict_result, dict):
            raise TypeError("Expected dict result for non-browser tool response")

        return types.FunctionResponse(
            name=executed_call.function_call.name,
            response=dict_result,
        )

    def execute(self, action: types.FunctionCall) -> ToolResult:
        name = action.name
        if name is None:
            raise ValueError(f"Unsupported function: {action}")

        handler = self._handlers.get(name)
        if handler is not None:
            return handler(action.args or {})

        custom_function = self._custom_functions.get(name)
        if custom_function is not None:
            return custom_function(**(action.args or {}))

        raise ValueError(f"Unsupported function: {action}")

    def _latest_artifact_metadata(self) -> dict[str, Any] | None:
        latest_artifacts_getter = getattr(
            self._browser_computer,
            "latest_artifact_metadata",
            None,
        )
        if callable(latest_artifacts_getter):
            latest_artifacts = latest_artifacts_getter()
            if isinstance(latest_artifacts, dict):
                return latest_artifacts
        return None


def prune_old_screenshot_parts(
    contents: list[types.Content],
    max_recent_turns_with_screenshots: int,
) -> None:
    turn_with_screenshots_found = 0
    for content in reversed(contents):
        if content.role != "user" or not content.parts:
            continue

        has_screenshot = False
        for part in content.parts:
            if (
                part.function_response
                and part.function_response.parts
                and part.function_response.name in PREDEFINED_COMPUTER_USE_FUNCTIONS
            ):
                has_screenshot = True
                break

        if not has_screenshot:
            continue

        turn_with_screenshots_found += 1
        if turn_with_screenshots_found <= max_recent_turns_with_screenshots:
            continue

        for part in content.parts:
            if (
                part.function_response
                and part.function_response.parts
                and part.function_response.name in PREDEFINED_COMPUTER_USE_FUNCTIONS
            ):
                part.function_response.parts = None
