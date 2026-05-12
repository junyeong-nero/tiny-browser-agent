from collections.abc import Callable
from functools import partial
import inspect
from typing import Any

from google.genai import types

from agents.task_scope import NavigationScope
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
from tools.check_by_ref import handle_check_by_ref
from tools.text_mode_tools import TEXT_MODE_TOOL_DESCRIPTORS
from tools.type_text_at import handle_type_text_at
from tools.type_by_ref import handle_type_by_ref
from tools.types import (
    CustomFunction,
    ExecutedCall,
    ToolBatchResult,
    ToolResult,
    is_env_state_result,
)
from tools.wait_5_seconds import handle_wait_5_seconds
from tools.wait_for_ref import handle_wait_for_ref
from tools.vision_mode_tools import VISION_MODE_TOOL_DESCRIPTORS


MAX_ARIA_SNAPSHOT_CHARS = 120_000

TOOL_HANDLERS = {
    "open_web_browser": handle_open_web_browser,
    "click_at": handle_click_at,
    "hover_at": handle_hover_at,
    "type_text_at": handle_type_text_at,
    "scroll_document": handle_scroll_document,
    "scroll_at": handle_scroll_at,
    "wait_5_seconds": handle_wait_5_seconds,
    "go_back": handle_go_back,
    "go_forward": handle_go_forward,
    "search": handle_search,
    "navigate": handle_navigate,
    "key_combination": handle_key_combination,
    "drag_and_drop": handle_drag_and_drop,
    "click_by_ref": handle_click_by_ref,
    "type_by_ref": handle_type_by_ref,
    "hover_by_ref": handle_hover_by_ref,
    "scroll_by_ref": handle_scroll_by_ref,
    "check_by_ref": handle_check_by_ref,
    "wait_for_ref": handle_wait_for_ref,
}


class BrowserToolExecutor:
    def __init__(
        self,
        browser_computer: PlaywrightBrowser,
        custom_functions: list[CustomFunction] | None = None,
        grounding: GroundingMode = "vision",
        navigation_scope: NavigationScope | None = None,
        use_computer_use_tools: bool = True,
    ) -> None:
        self._browser_computer = browser_computer
        self._grounding = grounding
        self._use_computer_use_tools = use_computer_use_tools
        self._navigation_scope = navigation_scope
        self._custom_functions = {
            custom_function.__name__: custom_function
            for custom_function in (custom_functions or [])
        }
        self._handlers: dict[str, Callable[[dict], ToolResult]] = {
            name: partial(handler, browser_computer)
            for name, handler in TOOL_HANDLERS.items()
        }

    def build_tools(
        self,
        build_function_declaration: Callable[[Callable[..., object]], types.FunctionDeclaration],
        excluded_predefined_functions: list[str] | None = None,
    ) -> list[types.Tool]:
        custom_declarations = [
            build_function_declaration(fn) for fn in self._custom_functions.values()
        ]

        excluded_names = set(excluded_predefined_functions or [])

        if self._grounding == "vision" and self._use_computer_use_tools:
            return [
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER,
                        excluded_predefined_functions=list(excluded_names),
                    )
                ),
                types.Tool(function_declarations=custom_declarations),
            ]

        if self._grounding == "vision":
            vision_declarations = self._build_unique_declarations(
                build_function_declaration,
                VISION_MODE_TOOL_DESCRIPTORS,
                excluded_names=excluded_names,
            )
            return [types.Tool(function_declarations=[*vision_declarations, *custom_declarations])]

        if self._grounding == "text":
            text_declarations = self._build_unique_declarations(
                build_function_declaration,
                TEXT_MODE_TOOL_DESCRIPTORS,
                excluded_names=excluded_names,
            )
            return [types.Tool(function_declarations=[*text_declarations, *custom_declarations])]

        # mixed: ComputerUse predefined tools + semantic ref tools + custom
        semantic_declarations = self._build_unique_declarations(
            build_function_declaration,
            TEXT_MODE_TOOL_DESCRIPTORS,
            excluded_names=excluded_names,
        )
        if self._use_computer_use_tools:
            return [
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER,
                        excluded_predefined_functions=list(excluded_names),
                    )
                ),
                types.Tool(function_declarations=[*semantic_declarations, *custom_declarations]),
            ]

        vision_declarations = self._build_unique_declarations(
            build_function_declaration,
            [*VISION_MODE_TOOL_DESCRIPTORS, *TEXT_MODE_TOOL_DESCRIPTORS],
            excluded_names=excluded_names,
        )
        return [types.Tool(function_declarations=[*vision_declarations, *custom_declarations])]

    @staticmethod
    def _build_unique_declarations(
        build_function_declaration: Callable[[Callable[..., object]], types.FunctionDeclaration],
        descriptors: list[Callable[..., object]],
        *,
        excluded_names: set[str],
    ) -> list[types.FunctionDeclaration]:
        declarations: list[types.FunctionDeclaration] = []
        seen = set()
        for descriptor in descriptors:
            name = descriptor.__name__
            if name in excluded_names or name in seen:
                continue
            seen.add(name)
            declarations.append(build_function_declaration(descriptor))
        return declarations

    def execute_call(self, action: types.FunctionCall) -> ExecutedCall:
        captures_actions = hasattr(type(self._browser_computer), "begin_action_capture")
        if captures_actions:
            self._browser_computer.begin_action_capture()
        result: ToolResult | None = None
        capture_updates = None
        persist_capture = False
        try:
            result = self.execute(action)
            persist_capture = is_env_state_result(result)
        finally:
            if captures_actions:
                capture_updates = self._end_action_capture(persist=persist_capture)
            if not persist_capture:
                self._clear_pending_action()
        artifacts = None
        if is_env_state_result(result):
            artifacts = self._latest_artifact_metadata()
            if isinstance(capture_updates, dict) and artifacts is not None:
                artifacts = {**artifacts, **capture_updates}
        return ExecutedCall(function_call=action, result=result, artifacts=artifacts)

    def _end_action_capture(self, *, persist: bool) -> dict[str, Any] | None:
        end_capture = getattr(self._browser_computer, "end_action_capture", None)
        if not callable(end_capture):
            return None

        try:
            parameters = inspect.signature(end_capture).parameters
        except (TypeError, ValueError):
            parameters = {}

        if "persist" in parameters:
            capture_updates = end_capture(persist=persist)
            return capture_updates if isinstance(capture_updates, dict) else None

        # Backward-compatible fallback for browser doubles or older facades that
        # cannot discard captures explicitly. We still stop the capture; callers
        # should only rely on updates when persistence was requested.
        capture_updates = end_capture()
        if persist and isinstance(capture_updates, dict):
            return capture_updates
        return None

    def _clear_pending_action(self) -> None:
        clear_pending_action = getattr(
            self._browser_computer,
            "clear_pending_action",
            None,
        )
        if callable(clear_pending_action):
            clear_pending_action()

    def supports_function(self, name: str | None) -> bool:
        """Return whether `name` can be executed by this executor."""
        if name is None:
            return False
        return name in self._handlers or name in self._custom_functions

    def serialize_function_response(
        self,
        executed_call: ExecutedCall,
        extra_response_fields: dict[str, Any] | None = None,
    ) -> types.FunctionResponse:
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
        response = self._build_env_state_response(env_state.url, extra_response_fields)
        parts = self._build_env_state_response_parts(env_state.screenshot)

        return types.FunctionResponse(
            name=executed_call.function_call.name,
            id=executed_call.function_call.id,
            response=response,
            parts=parts,
        )

    def _build_env_state_response(
        self,
        url: str,
        extra_response_fields: dict[str, Any] | None,
    ) -> dict[str, Any]:
        response_fields = dict(extra_response_fields or {})
        response: dict[str, Any] = {"url": url}
        tab_metadata = self._compact_tab_metadata()
        if tab_metadata:
            response.update(tab_metadata)
        if self._grounding in {"text", "mixed"}:
            snapshot = self._browser_computer.take_aria_snapshot()
            aria_snapshot, aria_metadata = compact_aria_snapshot_text(snapshot.text)
            response.update(
                {
                    "aria_snapshot": aria_snapshot,
                    **aria_metadata,
                }
            )
        response.update(response_fields)
        return response

    def _compact_tab_metadata(self) -> dict[str, Any]:
        list_tabs = getattr(self._browser_computer, "list_tabs", None)
        if not callable(list_tabs):
            return {}
        try:
            tabs_payload = list_tabs()
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(tabs_payload, dict):
            return {}
        metadata: dict[str, Any] = {}
        for key in ("active_tab_index", "tab_count"):
            value = tabs_payload.get(key)
            if isinstance(value, int):
                metadata[key] = value
        return metadata

    def _build_env_state_response_parts(
        self,
        screenshot: bytes,
    ) -> list[types.FunctionResponsePart] | None:
        if self._grounding not in {"vision", "mixed"}:
            return None
        return [
            types.FunctionResponsePart(
                inline_data=types.FunctionResponseBlob(
                    mime_type="image/png",
                    data=screenshot,
                )
            )
        ]

    def execute(self, action: types.FunctionCall) -> ToolResult:
        name = action.name
        if name is None:
            raise ValueError(f"Unsupported function: {action}")

        args = action.args or {}
        scope_violation = self._preflight_scope_violation(name, args)
        if scope_violation is not None:
            return scope_violation

        handler = self._handlers.get(name)
        if handler is not None:
            return self._guard_scoped_result(name, handler(args))

        custom_function = self._custom_functions.get(name)
        if custom_function is not None:
            filtered_args = self._filter_args(args, custom_function)
            return self._guard_scoped_result(name, custom_function(**filtered_args))

        raise ValueError(f"Unsupported function: {action}")

    def _preflight_scope_violation(
        self,
        name: str,
        args: dict[str, Any],
    ) -> dict[str, Any] | None:
        scope = self._navigation_scope
        if scope is None:
            return None

        url = args.get("url")
        if name in {"navigate", "open_web_browser"} and isinstance(url, str):
            if scope.blocks_search_url(url) or not scope.allows_url(url):
                return self._scope_error_payload(name, url)

        if name == "search":
            return self._scope_error_payload(name, "browser search page")

        return None

    def _guard_scoped_result(self, name: str, result: ToolResult) -> ToolResult:
        scope = self._navigation_scope
        if scope is None or not is_env_state_result(result):
            return result

        url = result.url
        if not url or url == "about:blank":
            return result
        if scope.allows_url(url):
            return result
        if not scope.blocks_search_url(url) and name in {"go_back", "go_forward"}:
            return result

        return self._scope_error_payload(name, url)

    def _scope_error_payload(self, name: str, url: str) -> dict[str, Any]:
        scope = self._navigation_scope
        message = (
            scope.violation_message(url)
            if scope is not None
            else f"Navigation blocked by task scope: {url}"
        )
        return {
            "status": "error",
            "tool_name": name,
            "error_type": "TaskScopeViolation",
            "error": message,
            "blocked_url": url,
        }

    def _filter_args(
        self, args: dict[str, Any], func: Callable[..., object]
    ) -> dict[str, Any]:
        sig = inspect.signature(func)
        valid_keys = {
            p.name for p in sig.parameters.values()
            if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
        }
        return {k: v for k, v in args.items() if k in valid_keys}

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


def compact_aria_snapshot_text(
    text: str,
    max_chars: int = MAX_ARIA_SNAPSHOT_CHARS,
) -> tuple[str, dict[str, Any]]:
    """Bound large ARIA snapshots before they enter model context."""
    if len(text) <= max_chars:
        return text, {}

    omitted_chars = len(text) - max_chars
    marker = (
        "\n... [ARIA snapshot truncated to stay within model context; "
        f"omitted {omitted_chars} characters. Use scroll/search/ref checks "
        "to inspect more of the page.]"
    )
    budget = max(max_chars - len(marker), 0)
    truncated = text[:budget].rstrip()
    newline_index = truncated.rfind("\n")
    if newline_index > max_chars // 2:
        truncated = truncated[:newline_index].rstrip()
    return (
        f"{truncated}{marker}",
        {
            "aria_snapshot_truncated": True,
            "aria_snapshot_original_chars": len(text),
        },
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
