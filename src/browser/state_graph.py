from typing import Any

from .state import BrowserState

MAX_DISPLAY_VALUE_LENGTH = 80
NO_PREVIOUS_VALUE = object()


def browser_state_to_graph(
    state: BrowserState,
    previous_state: BrowserState | None = None,
) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = [
        {"id": "browser", "label": "BrowserState", "type": "root", "isRoot": True},
        {"id": "page", "label": "PageState", "type": "group"},
        {"id": "viewport", "label": "ViewportState", "type": "group"},
        {"id": "interaction", "label": "InteractionState", "type": "group"},
    ]
    links: list[dict[str, Any]] = [
        {"source": "browser", "target": "page"},
        {"source": "browser", "target": "viewport"},
        {"source": "browser", "target": "interaction"},
    ]

    current_refs_count = len(state.interaction.available_refs)
    previous_refs_count = (
        len(previous_state.interaction.available_refs) if previous_state is not None else None
    )
    leaf_specs = [
        ("page.url", "page", "url", state.page.url, _previous(previous_state, "page.url"), "page.url"),
        (
            "page.title",
            "page",
            "title",
            state.page.title,
            _previous(previous_state, "page.title"),
            "page.title",
        ),
        (
            "page.html_path",
            "page",
            "html path",
            state.page.html_path,
            NO_PREVIOUS_VALUE,
            "page.html_path",
        ),
        (
            "page.a11y_path",
            "page",
            "a11y path",
            state.page.a11y_path,
            NO_PREVIOUS_VALUE,
            "page.a11y_path",
        ),
        (
            "viewport.size",
            "viewport",
            "viewport size",
            f"{state.viewport.width}×{state.viewport.height}",
            _previous_viewport_size(previous_state),
            "viewport.width/height",
        ),
        (
            "viewport.scroll",
            "viewport",
            "scroll",
            f"x={state.viewport.scroll_x}, y={state.viewport.scroll_y}",
            _previous_scroll(previous_state),
            "viewport.scroll_x/y",
        ),
        (
            "viewport.screenshot",
            "viewport",
            "screenshot",
            f"{len(state.viewport.screenshot)} bytes",
            NO_PREVIOUS_VALUE,
            "viewport.screenshot",
        ),
        (
            "interaction.focused_element",
            "interaction",
            "focused element",
            state.interaction.focused_element,
            _previous(previous_state, "interaction.focused_element"),
            "interaction.focused_element",
        ),
        (
            "interaction.available_refs",
            "interaction",
            "available refs",
            current_refs_count,
            previous_refs_count,
            "interaction.available_refs",
        ),
        (
            "interaction.last_action",
            "interaction",
            "last action",
            state.interaction.last_action,
            NO_PREVIOUS_VALUE,
            "interaction.last_action",
        ),
    ]

    for node_id, parent_id, label, value, previous_value, source_path in leaf_specs:
        nodes.append(_leaf_node(node_id, label, value, previous_value, source_path))
        links.append({"source": parent_id, "target": node_id})

    return {"nodes": nodes, "links": links}


def _leaf_node(
    node_id: str,
    label: str,
    value: Any,
    previous_value: Any,
    source_path: str,
) -> dict[str, Any]:
    full_value = "" if value is None else str(value)
    node: dict[str, Any] = {
        "id": node_id,
        "label": label,
        "type": "leaf",
        "value": _display_value(full_value),
        "full_value": full_value,
        "source_path": source_path,
    }
    if previous_value is not NO_PREVIOUS_VALUE and previous_value != value:
        node["changed"] = True
        node["previous_value"] = "" if previous_value is None else str(previous_value)
        node["current_value"] = full_value
    return node


def _display_value(value: str) -> str:
    if len(value) <= MAX_DISPLAY_VALUE_LENGTH:
        return value
    return value[: MAX_DISPLAY_VALUE_LENGTH - 1] + "…"


def _previous(previous_state: BrowserState | None, path: str) -> Any:
    if previous_state is None:
        return NO_PREVIOUS_VALUE
    if path == "page.url":
        return previous_state.page.url
    if path == "page.title":
        return previous_state.page.title
    if path == "interaction.focused_element":
        return previous_state.interaction.focused_element
    return None


def _previous_viewport_size(previous_state: BrowserState | None) -> Any:
    if previous_state is None:
        return NO_PREVIOUS_VALUE
    return f"{previous_state.viewport.width}×{previous_state.viewport.height}"


def _previous_scroll(previous_state: BrowserState | None) -> Any:
    if previous_state is None:
        return NO_PREVIOUS_VALUE
    return f"x={previous_state.viewport.scroll_x}, y={previous_state.viewport.scroll_y}"
