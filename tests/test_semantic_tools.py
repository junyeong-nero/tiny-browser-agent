import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from browser.aria_snapshot import NodeInfo, build_aria_snapshot
from browser.playwright import EnvState


def _make_browser_with_snapshot(yaml: str = None):
    """Create a mock PlaywrightBrowser with a cached aria ref map."""
    browser = MagicMock()
    snapshot_yaml = yaml or "- textbox \"Search\"\n- button \"Submit\"\n"
    snapshot = build_aria_snapshot(snapshot_yaml, "https://example.com")
    browser._aria_ref_map = snapshot.ref_map
    browser._page = MagicMock()
    browser._page.wait_for_load_state = MagicMock()
    fake_state = EnvState(screenshot=b"fake", url="https://example.com")
    browser.current_state.return_value = fake_state
    browser.key_combination.return_value = fake_state
    return browser, snapshot


class TestClickByRef:
    def test_happy_path(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        browser.resolve_ref.return_value = mock_locator

        from tools.click_by_ref import handle_click_by_ref
        result = handle_click_by_ref(browser, {"ref": 1})

        browser.resolve_ref.assert_called_once_with(1)
        browser._mark_last_action.assert_called_once_with("click_by_ref")
        mock_locator.click.assert_called_once_with(timeout=5000)
        assert result == browser.current_state.return_value

    def test_retries_with_force_when_pointer_events_are_intercepted(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        mock_locator.click.side_effect = [
            PlaywrightTimeoutError("subtree intercepts pointer events"),
            None,
        ]
        browser.resolve_ref.return_value = mock_locator

        from tools.click_by_ref import handle_click_by_ref
        result = handle_click_by_ref(browser, {"ref": 1})

        browser.resolve_ref.assert_called_once_with(1)
        assert mock_locator.click.call_args_list[0].kwargs == {"timeout": 5000}
        assert mock_locator.click.call_args_list[1].kwargs == {
            "force": True,
            "timeout": 5000,
        }
        assert result == browser.current_state.return_value

    def test_stale_ref_raises(self):
        browser, _ = _make_browser_with_snapshot()
        browser.resolve_ref.side_effect = ValueError("ref 99 is stale, request a new snapshot")

        from tools.click_by_ref import handle_click_by_ref
        with pytest.raises(ValueError, match="stale"):
            handle_click_by_ref(browser, {"ref": 99})


class TestTypeByRef:
    def test_happy_path(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        browser.resolve_ref.return_value = mock_locator

        from tools.type_by_ref import handle_type_by_ref
        result = handle_type_by_ref(browser, {"ref": 1, "text": "hello"})

        browser.resolve_ref.assert_called_once_with(1)
        browser._mark_last_action.assert_called_once_with("type_by_ref")
        mock_locator.click.assert_called_once_with(timeout=5000)
        mock_locator.fill.assert_called_once_with("hello")
        browser.key_combination.assert_not_called()
        assert result == browser.current_state.return_value

    def test_press_enter(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        browser.resolve_ref.return_value = mock_locator

        from tools.type_by_ref import handle_type_by_ref
        result = handle_type_by_ref(browser, {"ref": 1, "text": "hello", "press_enter": True})

        browser._mark_last_action.assert_called_once_with("type_by_ref")
        browser.key_combination.assert_called_once_with(["Enter"])
        assert result == browser.key_combination.return_value

    def test_stale_ref_raises(self):
        browser, _ = _make_browser_with_snapshot()
        browser.resolve_ref.side_effect = ValueError("ref 99 is stale, request a new snapshot")

        from tools.type_by_ref import handle_type_by_ref
        with pytest.raises(ValueError, match="stale"):
            handle_type_by_ref(browser, {"ref": 99, "text": "hello"})


class TestHoverByRef:
    def test_happy_path(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        browser.resolve_ref.return_value = mock_locator

        from tools.hover_by_ref import handle_hover_by_ref
        result = handle_hover_by_ref(browser, {"ref": 1})

        browser.resolve_ref.assert_called_once_with(1)
        browser._mark_last_action.assert_called_once_with("hover_by_ref")
        mock_locator.hover.assert_called_once()
        assert result == browser.current_state.return_value

    def test_stale_ref_raises(self):
        browser, _ = _make_browser_with_snapshot()
        browser.resolve_ref.side_effect = ValueError("ref 5 is stale, request a new snapshot")

        from tools.hover_by_ref import handle_hover_by_ref
        with pytest.raises(ValueError, match="stale"):
            handle_hover_by_ref(browser, {"ref": 5})


class TestScrollByRef:
    def test_happy_path_with_bounding_box(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        mock_locator.bounding_box.return_value = {"x": 100, "y": 200, "width": 50, "height": 30}
        browser.resolve_ref.return_value = mock_locator
        fake_state = EnvState(screenshot=b"fake", url="https://example.com")
        browser.scroll_at.return_value = fake_state

        from tools.scroll_by_ref import handle_scroll_by_ref
        result = handle_scroll_by_ref(browser, {"ref": 1, "direction": "down"})

        browser.scroll_at.assert_called_once_with(125, 215, "down")
        assert result == fake_state

    def test_fallback_to_scroll_document_when_no_bounding_box(self):
        browser, snapshot = _make_browser_with_snapshot()
        mock_locator = MagicMock()
        mock_locator.bounding_box.return_value = None
        browser.resolve_ref.return_value = mock_locator
        fake_state = EnvState(screenshot=b"fake", url="https://example.com")
        browser.scroll_document.return_value = fake_state

        from tools.scroll_by_ref import handle_scroll_by_ref
        result = handle_scroll_by_ref(browser, {"ref": 1, "direction": "up"})

        browser.scroll_document.assert_called_once_with("up")
        assert result == fake_state
