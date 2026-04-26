from typing import Any

import pydantic


class PageState(pydantic.BaseModel):
    url: str
    title: str | None = None
    html_path: str | None = None
    a11y_path: str | None = None


class ViewportState(pydantic.BaseModel):
    screenshot: bytes
    width: int = 0
    height: int = 0
    scroll_x: int = 0
    scroll_y: int = 0


class InteractionState(pydantic.BaseModel):
    focused_element: str | None = None
    available_refs: list[int] = pydantic.Field(default_factory=list)
    last_action: str | None = None


class BrowserState(pydantic.BaseModel):
    page: PageState
    viewport: ViewportState
    interaction: InteractionState = pydantic.Field(default_factory=InteractionState)

    @pydantic.model_validator(mode="before")
    @classmethod
    def accept_legacy_env_state_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "page" in data or "viewport" in data:
            return data
        if "url" not in data or "screenshot" not in data:
            return data

        return {
            "page": PageState(url=data["url"]),
            "viewport": ViewportState(screenshot=data["screenshot"]),
            "interaction": InteractionState(),
        }

    @property
    def url(self) -> str:
        return self.page.url

    @property
    def screenshot(self) -> bytes:
        return self.viewport.screenshot


class EnvState(BrowserState):
    """Compatibility state name kept for existing browser/tool contracts."""

    def __init__(
        self,
        *,
        screenshot: bytes | None = None,
        url: str | None = None,
        **data: Any,
    ) -> None:
        if screenshot is not None:
            data["screenshot"] = screenshot
        if url is not None:
            data["url"] = url
        super().__init__(**data)
