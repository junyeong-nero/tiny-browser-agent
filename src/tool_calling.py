from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeAlias, TypeGuard

from google.genai import types

from computers import Computer, EnvState


PREDEFINED_COMPUTER_USE_FUNCTIONS = [
    "open_web_browser",
    "click_at",
    "hover_at",
    "type_text_at",
    "scroll_document",
    "scroll_at",
    "wait_5_seconds",
    "go_back",
    "go_forward",
    "search",
    "navigate",
    "key_combination",
    "drag_and_drop",
]

class EnvStateLike(Protocol):
    screenshot: bytes
    url: str


def is_env_state_result(result: object) -> TypeGuard[EnvStateLike]:
    return (
        not isinstance(result, dict)
        and hasattr(result, "screenshot")
        and hasattr(result, "url")
    )


ToolResult: TypeAlias = EnvStateLike | dict[str, Any]
CustomFunction: TypeAlias = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ExecutedCall:
    function_call: types.FunctionCall
    result: ToolResult
    artifacts: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolBatchResult:
    status: Literal["CONTINUE", "COMPLETE"]
    function_responses: list[types.FunctionResponse]


class BrowserToolExecutor:
    def __init__(
        self,
        browser_computer: Computer,
        custom_functions: list[CustomFunction] | None = None,
    ) -> None:
        self._browser_computer = browser_computer
        self._custom_functions = {
            custom_function.__name__: custom_function
            for custom_function in (custom_functions or [])
        }
        self._handlers = {
            "open_web_browser": self._handle_open_web_browser,
            "click_at": self._handle_click_at,
            "hover_at": self._handle_hover_at,
            "type_text_at": self._handle_type_text_at,
            "scroll_document": self._handle_scroll_document,
            "scroll_at": self._handle_scroll_at,
            "wait_5_seconds": self._handle_wait_5_seconds,
            "go_back": self._handle_go_back,
            "go_forward": self._handle_go_forward,
            "search": self._handle_search,
            "navigate": self._handle_navigate,
            "key_combination": self._handle_key_combination,
            "drag_and_drop": self._handle_drag_and_drop,
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

    def denormalize_x(self, x: int) -> int:
        return int(x / 1000 * self._browser_computer.screen_size()[0])

    def denormalize_y(self, y: int) -> int:
        return int(y / 1000 * self._browser_computer.screen_size()[1])

    def _handle_open_web_browser(self, args: dict) -> EnvState:
        del args
        return self._browser_computer.open_web_browser()

    def _handle_click_at(self, args: dict) -> EnvState:
        return self._browser_computer.click_at(
            x=self.denormalize_x(args["x"]),
            y=self.denormalize_y(args["y"]),
        )

    def _handle_hover_at(self, args: dict) -> EnvState:
        return self._browser_computer.hover_at(
            x=self.denormalize_x(args["x"]),
            y=self.denormalize_y(args["y"]),
        )

    def _handle_type_text_at(self, args: dict) -> EnvState:
        return self._browser_computer.type_text_at(
            x=self.denormalize_x(args["x"]),
            y=self.denormalize_y(args["y"]),
            text=args["text"],
            press_enter=args.get("press_enter", False),
            clear_before_typing=args.get("clear_before_typing", True),
        )

    def _handle_scroll_document(self, args: dict) -> EnvState:
        return self._browser_computer.scroll_document(args["direction"])

    def _handle_scroll_at(self, args: dict) -> EnvState:
        direction = args["direction"]
        magnitude = args.get("magnitude", 800)
        if direction in ("up", "down"):
            magnitude = self.denormalize_y(magnitude)
        elif direction in ("left", "right"):
            magnitude = self.denormalize_x(magnitude)
        else:
            raise ValueError("Unknown direction: ", direction)

        return self._browser_computer.scroll_at(
            x=self.denormalize_x(args["x"]),
            y=self.denormalize_y(args["y"]),
            direction=direction,
            magnitude=magnitude,
        )

    def _handle_wait_5_seconds(self, args: dict) -> EnvState:
        del args
        return self._browser_computer.wait_5_seconds()

    def _handle_go_back(self, args: dict) -> EnvState:
        del args
        return self._browser_computer.go_back()

    def _handle_go_forward(self, args: dict) -> EnvState:
        del args
        return self._browser_computer.go_forward()

    def _handle_search(self, args: dict) -> EnvState:
        del args
        return self._browser_computer.search()

    def _handle_navigate(self, args: dict) -> EnvState:
        return self._browser_computer.navigate(args["url"])

    def _handle_key_combination(self, args: dict) -> EnvState:
        return self._browser_computer.key_combination(args["keys"].split("+"))

    def _handle_drag_and_drop(self, args: dict) -> EnvState:
        return self._browser_computer.drag_and_drop(
            x=self.denormalize_x(args["x"]),
            y=self.denormalize_y(args["y"]),
            destination_x=self.denormalize_x(args["destination_x"]),
            destination_y=self.denormalize_y(args["destination_y"]),
        )


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
