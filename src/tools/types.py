from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeAlias, TypeGuard

from google.genai import types

from browser import EnvState, PlaywrightBrowser


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
TOOL_ARGUMENT_ERROR_KEY = "_tool_argument_error"


@dataclass(frozen=True)
class ExecutedCall:
    function_call: types.FunctionCall
    result: ToolResult
    artifacts: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolBatchResult:
    status: Literal["CONTINUE", "COMPLETE"]
    function_responses: list[types.FunctionResponse]


def build_tool_error_payload(
    *,
    tool_name: str | None,
    error_type: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "tool_name": tool_name,
        "error_type": error_type,
        "error": error_message,
    }


def build_tool_argument_parse_error(
    *,
    tool_name: str | None,
    raw_arguments: str,
    exc: Exception,
) -> dict[str, Any]:
    error_message = (
        f"Malformed tool arguments JSON for {tool_name or '<missing name>'}: "
        f"{type(exc).__name__}: {exc}"
    )
    return build_tool_error_payload(
        tool_name=tool_name,
        error_type=type(exc).__name__,
        error_message=error_message,
    ) | {"raw_arguments": raw_arguments}


def extract_tool_argument_error(args: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(args, dict):
        return None
    error_payload = args.get(TOOL_ARGUMENT_ERROR_KEY)
    if isinstance(error_payload, dict):
        return error_payload
    return None


def denormalize_x(x: int, computer: PlaywrightBrowser) -> int:
    width = computer.screen_size()[0]
    return _denormalize_coordinate(x, width)


def denormalize_y(y: int, computer: PlaywrightBrowser) -> int:
    height = computer.screen_size()[1]
    return _denormalize_coordinate(y, height)


def _denormalize_coordinate(value: int, extent: int) -> int:
    if extent <= 0:
        return 0
    normalized = max(0, min(1000, value))
    return min(extent - 1, int(normalized / 1000 * extent))
