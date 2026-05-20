import re
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from simple_ui.server import app
from ui.bridge import reset_task_state_for_tests


SIMPLE_PANEL_HTML_ONLY = Path("src/simple_ui/panel.html").read_text(encoding="utf-8")
SIMPLE_PANEL_CSS = Path("src/simple_ui/static/panel.css").read_text(encoding="utf-8")
SIMPLE_GRAPH_JS = Path("src/simple_ui/static/graph.js").read_text(encoding="utf-8")
SIMPLE_PANEL_JS = Path("src/simple_ui/static/panel.js").read_text(encoding="utf-8")
SIMPLE_PANEL = SIMPLE_PANEL_HTML_ONLY + "\n" + SIMPLE_PANEL_CSS + "\n" + SIMPLE_GRAPH_JS + "\n" + SIMPLE_PANEL_JS


def test_simple_panel_loads_own_static_assets():
    assert '<link rel="stylesheet" href="/static/panel.css">' in SIMPLE_PANEL_HTML_ONLY
    assert '<script src="/static/graph.js"></script>' in SIMPLE_PANEL_HTML_ONLY
    assert '<script src="/static/panel.js"></script>' in SIMPLE_PANEL_HTML_ONLY
    assert "d3.v7.min.js" not in SIMPLE_PANEL_HTML_ONLY
    assert '<style>' not in SIMPLE_PANEL_HTML_ONLY
    assert '<script>' not in SIMPLE_PANEL_HTML_ONLY


def test_simple_panel_keeps_full_ui_chrome_and_timeline_surface():
    assert 'class="brand-mark"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="dot"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="status-label"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="theme-toggle"' in SIMPLE_PANEL_HTML_ONLY
    assert "<span>New</span>" in SIMPLE_PANEL_HTML_ONLY
    assert "<span>History</span>" in SIMPLE_PANEL_HTML_ONLY
    assert 'id="replay-controls"' in SIMPLE_PANEL_HTML_ONLY
    assert 'data-view="timeline"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="timeline"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="input-shell"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="input"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="agent-model"' in SIMPLE_PANEL_HTML_ONLY
    assert "Timeline" in SIMPLE_PANEL_HTML_ONLY

    assert 'id="left-sidebar"' not in SIMPLE_PANEL_HTML_ONLY
    assert 'id="left-resizer"' not in SIMPLE_PANEL_HTML_ONLY
    assert 'id="right-sidebar"' in SIMPLE_PANEL_HTML_ONLY
    assert 'class="side-panel simple-screenshot-panel"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="right-resizer"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="side-step-title"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="side-replay"' in SIMPLE_PANEL_HTML_ONLY
    assert 'id="simple-action-details"' in SIMPLE_PANEL_HTML_ONLY
    assert 'data-view="graph"' not in SIMPLE_PANEL_HTML_ONLY
    assert 'id="graph-wrap"' not in SIMPLE_PANEL_HTML_ONLY
    assert 'id="graph-svg"' not in SIMPLE_PANEL_HTML_ONLY


def test_simple_panel_uses_full_panel_assets_with_simple_layout_overrides():
    assert "const themeToggle = document.getElementById('theme-toggle');" in SIMPLE_PANEL_JS
    assert "function setupTheme()" in SIMPLE_PANEL_JS
    assert "function beginActionStepGroup(stepId)" in SIMPLE_PANEL_JS
    assert "function replayArtifactHref(path, expectedDir = 'history')" in SIMPLE_GRAPH_JS
    assert "function renderActionArtifacts(artifacts)" in SIMPLE_GRAPH_JS
    assert "function renderRightPanelAuxiliarySections(_inference, _artifacts)" in SIMPLE_GRAPH_JS
    assert "function recordActionExecution(_event) {}" in SIMPLE_GRAPH_JS
    assert "body.simple-ui" in SIMPLE_PANEL_CSS
    assert 'grid-template-areas:\n    "header header        header"\n    "right-aside right-resizer main"\n    "right-aside right-resizer footer";' in SIMPLE_PANEL_CSS
    assert "--right-aside-w: 360px;" in SIMPLE_PANEL_CSS
    assert "body.simple-ui #right-resizer" in SIMPLE_PANEL_CSS
    assert "body.simple-ui aside#right-sidebar" in SIMPLE_PANEL_CSS
    assert "margin: 16px 8px 16px 16px;" in SIMPLE_PANEL_CSS
    assert "body.simple-ui #left-sidebar" in SIMPLE_PANEL_CSS
    assert "body.simple-ui [data-view=\"graph\"]" in SIMPLE_PANEL_CSS


def test_simple_panel_right_panel_shows_only_step_screenshot():
    assert "function renderActionScreenshotCard(label, href)" in SIMPLE_GRAPH_JS
    artifact_renderer = SIMPLE_GRAPH_JS.split("function renderActionArtifacts(artifacts)", 1)[1].split(
        "function renderRightPanelAuxiliarySections", 1
    )[0]

    assert "after_screenshot_path || artifacts.screenshot_path" in artifact_renderer
    assert "before_screenshot_path" in artifact_renderer
    assert "simple-screenshot-link" in SIMPLE_GRAPH_JS
    assert "action_clip_gif_path" not in artifact_renderer
    assert "action_gif_path" not in artifact_renderer
    assert "video_path" not in artifact_renderer
    assert "renderBeforeAfterCompare" not in artifact_renderer
    assert "artifact-label" not in artifact_renderer

    store_artifacts = SIMPLE_PANEL_JS.split("function storeArtifactsForStep(stepId, artifacts)", 1)[1].split(
        "function upsertActionSummary", 1
    )[0]
    assert "if (selectedTimelineStepId == null)" in store_artifacts
    assert "renderActionStepAdditionalInfo(key);" in store_artifacts
    assert "Action step #${key}" in SIMPLE_PANEL_JS
    assert "const simpleActionDetails = document.getElementById('simple-action-details');" in SIMPLE_PANEL_JS
    assert "function renderSimpleActionDetails(calls)" in SIMPLE_PANEL_JS
    assert "renderSimpleActionDetails(calls);" in SIMPLE_PANEL_JS
    assert "simple-tool-label\">tool" in SIMPLE_PANEL_JS
    assert "simple-tool-label\">arguments" in SIMPLE_PANEL_JS
    assert "body.simple-ui .simple-screenshot-panel .side-step-title" in SIMPLE_PANEL_CSS
    assert "text-align: left;" in SIMPLE_PANEL_CSS
    assert ".simple-screenshot-link img" in SIMPLE_PANEL_CSS
    assert "object-position: center center;" in SIMPLE_PANEL_CSS
    sheet_body_css = SIMPLE_PANEL_CSS.split(
        "body.simple-ui .simple-screenshot-panel .sheet-body {", 1
    )[1].split("}", 1)[0]
    assert "grid-template-rows: auto minmax(0, 1fr) auto;" in sheet_body_css
    assert "scrollbar-gutter: stable both-edges;" in sheet_body_css
    screenshot_body_css = SIMPLE_PANEL_CSS.split(
        "body.simple-ui .simple-screenshot-body {", 1
    )[1].split("}", 1)[0]
    assert "padding: 6px 16px;" in screenshot_body_css
    assert "body.simple-ui .simple-action-details" in SIMPLE_PANEL_CSS


def test_simple_panel_static_assets_are_served():
    client = TestClient(app)
    for path, expected in (
        ("/static/panel.css", "text/css"),
        ("/static/graph.js", "javascript"),
        ("/static/panel.js", "javascript"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.headers["content-type"]
        assert response.headers["cache-control"] == "no-store"

    html = client.get("/")
    assert html.status_code == 200
    assert html.headers["cache-control"] == "no-store"
    assert "/static/panel.css" in html.text
    assert "/static/graph.js" in html.text
    assert "/static/panel.js" in html.text


def test_simple_panel_served_html_cache_busts_local_static_assets():
    html = TestClient(app).get("/")

    assert html.status_code == 200
    for asset in ("panel.css", "graph.js", "panel.js"):
        assert re.search(rf"/static/{re.escape(asset)}\?v=\d+", html.text)


def test_simple_task_endpoint_uses_shared_bridge_queue():
    reset_task_state_for_tests()
    client = TestClient(app)
    with patch("simple_ui.server.task_queue") as mock_queue:
        response = client.post("/task", json={"query": "use simple ui"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    mock_queue.put.assert_called_once_with("use simple ui")
    reset_task_state_for_tests()
