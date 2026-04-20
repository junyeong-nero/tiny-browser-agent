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


@dataclass(frozen=True)
class ExecutedCall:
    function_call: types.FunctionCall
    result: ToolResult
    artifacts: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolBatchResult:
    status: Literal["CONTINUE", "COMPLETE"]
    function_responses: list[types.FunctionResponse]


def denormalize_x(x: int, computer: PlaywrightBrowser) -> int:
    return int(x / 1000 * computer.screen_size()[0])


def denormalize_y(y: int, computer: PlaywrightBrowser) -> int:
    return int(y / 1000 * computer.screen_size()[1])
