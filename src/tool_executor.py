from collections.abc import Callable
import inspect
from typing import Any

from google.genai import types

from agents.types import GroundingMode
from browser import PlaywrightBrowser
from tools.click_at import handle_click_at
from tools.click_by_ref import handle_click_by_ref
from tools.constants import PREDEFINED_COMPUTER_USE_FUNCTIONS
from tools.drag_and_drop import handle_drag_and_drop
from tools.go_back import handle_go_back
from tools.go_forward import handle_go_forward
from tools.hover_at import handle_hover_at
from tools.hover_by_ref import handle_hover_by_ref
from tools.key_combination import handle_key_combination
from tools.navigate import handle_navigate
from tools.open_web_browser import handle_open_web_browser
from tools.scroll_at import handle_scroll_at
from tools.scroll_by_ref import handle_scroll_by_ref
from tools.scroll_document import handle_scroll_document
from tools.search import handle_search
from tools.text_mode_tools import TEXT_MODE_TOOL_DESCRIPTORS
from tools.type_text_at import handle_type_text_at
from tools.type_by_ref import handle_type_by_ref
from tools.types import (
    CustomFunction,
    ExecutedCall,
    ToolBatchResult,
    ToolResult,
    denormalize_x as _denormalize_x,
    denormalize_y as _denormalize_y,
    is_env_state_result,
)
from tools.wait_5_seconds import handle_wait_5_seconds


class BrowserToolExecutor:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        custom_functions: list[CustomFunction] | None = None,
        grounding: GroundingMode = "vision",
    ) -> None:
        self._browser_computer = browser_computer
        self._grounding = grounding
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
            # Semantic ref-based tools
            "click_by_ref": lambda args: handle_click_by_ref(browser_computer, args),
            "type_by_ref": lambda args: handle_type_by_ref(browser_computer, args),
            "hover_by_ref": lambda args: handle_hover_by_ref(browser_computer, args),
            "scroll_by_ref": lambda args: handle_scroll_by_ref(browser_computer, args),
        }

    def build_tools(
        self,
        build_function_declaration: Callable[[Callable[..., object]], types.FunctionDeclaration],
        excluded_predefined_functions: list[str] | None = None,
    ) -> list[types.Tool]:
        custom_declarations = [
            build_function_declaration(fn) for fn in self._custom_functions.values()
        ]

        if self._grounding == "vision":
            return [
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER,
                        excluded_predefined_functions=excluded_predefined_functions or [],
                    )
                ),
                types.Tool(function_declarations=custom_declarations),
            ]

        if self._grounding == "text":
            text_declarations = [
                build_function_declaration(fn) for fn in TEXT_MODE_TOOL_DESCRIPTORS
            ]
            return [types.Tool(function_declarations=[*text_declarations, *custom_declarations])]

        # mixed: ComputerUse predefined tools + semantic ref tools + custom
        semantic_declarations = [
            build_function_declaration(fn) for fn in TEXT_MODE_TOOL_DESCRIPTORS
        ]
        return [
            types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER,
                    excluded_predefined_functions=excluded_predefined_functions or [],
                )
            ),
            types.Tool(function_declarations=[*semantic_declarations, *custom_declarations]),
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

        if not is_env_state_result(executed_call.result):
            dict_result = executed_call.result
            if not isinstance(dict_result, dict):
                raise TypeError("Expected dict result for non-browser tool response")
            return types.FunctionResponse(
                name=executed_call.function_call.name,
                id=executed_call.function_call.id,
                response=dict_result,
            )

        env_state = executed_call.result

        if self._grounding == "vision":
            return types.FunctionResponse(
                name=executed_call.function_call.name,
                id=executed_call.function_call.id,
                response={"url": env_state.url, **response_fields},
                parts=[
                    types.FunctionResponsePart(
                        inline_data=types.FunctionResponseBlob(
                            mime_type="image/png",
                            data=env_state.screenshot,
                        )
                    )
                ],
            )

        if self._grounding == "text":
            snapshot = self._browser_computer.take_aria_snapshot()
            return types.FunctionResponse(
                name=executed_call.function_call.name,
                id=executed_call.function_call.id,
                response={
                    "url": env_state.url,
                    "aria_snapshot": snapshot.text,
                    **response_fields,
                },
            )

        # mixed: both screenshot and ARIA snapshot
        snapshot = self._browser_computer.take_aria_snapshot()
        return types.FunctionResponse(
            name=executed_call.function_call.name,
            id=executed_call.function_call.id,
            response={
                "url": env_state.url,
                "aria_snapshot": snapshot.text,
                **response_fields,
            },
            parts=[
                types.FunctionResponsePart(
                    inline_data=types.FunctionResponseBlob(
                        mime_type="image/png",
                        data=env_state.screenshot,
                    )
                )
            ],
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
            args = self._filter_args(action.args or {}, custom_function)
            return custom_function(**args)

        raise ValueError(f"Unsupported function: {action}")

    def _filter_args(
        self, args: dict[str, Any], func: Callable[..., object]
    ) -> dict[str, Any]:
        sig = inspect.signature(func)
        valid_keys = {
            p.name for p in sig.parameters.values()
            if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
        }
        return {k: v for k, v in args.items() if k in valid_keys}

    def denormalize_x(self, x: int) -> int:
        return _denormalize_x(x, self._browser_computer)

    def denormalize_y(self, y: int) -> int:
        return _denormalize_y(y, self._browser_computer)

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


def prune_old_aria_parts(
    contents: list[types.Content],
    max_recent_turns_with_aria: int,
) -> None:
    """Remove aria_snapshot from old function responses to limit context size."""
    turns_found = 0
    for content in reversed(contents):
        if content.role != "user" or not content.parts:
            continue

        has_aria = any(
            part.function_response
            and isinstance(part.function_response.response, dict)
            and "aria_snapshot" in part.function_response.response
            for part in content.parts
        )
        if not has_aria:
            continue

        turns_found += 1
        if turns_found <= max_recent_turns_with_aria:
            continue

        for part in content.parts:
            if (
                part.function_response
                and isinstance(part.function_response.response, dict)
                and "aria_snapshot" in part.function_response.response
            ):
                part.function_response.response = {
                    k: v
                    for k, v in part.function_response.response.items()
                    if k != "aria_snapshot"
                }
