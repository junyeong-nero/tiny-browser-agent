import re
from pathlib import Path

from fastapi.testclient import TestClient

from ui.server import app


PANEL_HTML_ONLY = Path("src/ui/panel.html").read_text(encoding="utf-8")
PANEL_CSS = Path("src/ui/static/panel.css").read_text(encoding="utf-8")
PANEL_JS = Path("src/ui/static/panel.js").read_text(encoding="utf-8")
GRAPH_JS = Path("src/ui/static/graph.js").read_text(encoding="utf-8")
# Existing static-contract tests search the asset that now owns the code/CSS.
PANEL_HTML = PANEL_HTML_ONLY + "\n" + PANEL_CSS + "\n" + PANEL_JS + "\n" + GRAPH_JS




def test_panel_loads_split_static_assets():
    assert '<link rel="stylesheet" href="/static/panel.css">' in PANEL_HTML_ONLY
    assert '<script src="https://d3js.org/d3.v7.min.js"></script>' in PANEL_HTML_ONLY
    assert '<script src="/static/graph.js"></script>' in PANEL_HTML_ONLY
    assert '<script src="/static/panel.js"></script>' in PANEL_HTML_ONLY
    assert '<style>' not in PANEL_HTML_ONLY
    assert '<script>' not in PANEL_HTML_ONLY


def test_panel_static_assets_are_served():
    client = TestClient(app)
    for path, expected in (
        ('/static/panel.css', 'text/css'),
        ('/static/panel.js', 'javascript'),
        ('/static/graph.js', 'javascript'),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.headers['content-type']
        assert response.headers['cache-control'] == 'no-store'

    html = client.get('/')
    assert html.status_code == 200
    assert html.headers['cache-control'] == 'no-store'
    assert '/static/panel.css' in html.text
    assert '/static/graph.js' in html.text
    assert '/static/panel.js' in html.text


def test_panel_served_html_cache_busts_local_static_assets():
    html = TestClient(app).get('/')

    assert html.status_code == 200
    for asset in ('panel.css', 'graph.js', 'panel.js'):
        assert re.search(rf'/static/{re.escape(asset)}\?v=\d+', html.text)


def test_panel_model_placeholder_is_not_hardcoded_to_gemini():
    assert '<span id="agent-model">gemini</span>' not in PANEL_HTML
    assert '<span id="agent-model">—</span>' in PANEL_HTML
    assert 'placeholder="Describe what you want the agent to do…"' in PANEL_HTML
    input_agent_html = PANEL_HTML_ONLY.split('<div class="input-agent">', 1)[1].split("</div>", 1)[0]
    assert "browser-agent" not in input_agent_html
    assert "agent-name" not in input_agent_html
    input_controls_css = PANEL_HTML.split(".input-controls {", 1)[1].split("}", 1)[0]
    input_agent_css = PANEL_HTML.split(".input-agent {", 1)[1].split("}", 1)[0]
    textarea_css = PANEL_HTML.split("textarea {", 1)[1].split("}", 1)[0]
    assert "justify-content: flex-end;" in input_controls_css
    assert "margin-left: auto;" in input_agent_css
    assert "width: 100%;" in textarea_css


def test_panel_updates_model_name_from_session_ready_event():
    assert "const agentModel  = document.getElementById('agent-model');" in PANEL_HTML
    assert "function setAgentModel(modelName)" in PANEL_HTML
    assert "setAgentModel(ev.model_name);" in PANEL_HTML


def test_panel_replan_preserves_existing_subgoals_before_failed_one():
    assert "let pendingReplanFailedSubgoalId = null;" in PANEL_HTML
    assert "function replaceSubgoalsAfterFailed(failedId, revisedList)" in PANEL_HTML
    assert "subgoals = subgoals.slice(0, failedIdx + 1).concat(revisedSubgoals);" in PANEL_HTML


def test_panel_replanned_event_replaces_only_after_failed_subgoal():
    replanned_case = PANEL_HTML.split("case 'planner_replanned':", 1)[1].split(
        "case 'subgoal_started':", 1
    )[0]
    assert "replaceSubgoalsAfterFailed(" in replanned_case
    assert "ev.failed_subgoal_id != null ? ev.failed_subgoal_id : pendingReplanFailedSubgoalId" in replanned_case
    assert "setSubgoals(items);" not in replanned_case


def test_panel_graph_tab_shows_only_trajectory_graph():
    assert 'data-graph-mode="state"' not in PANEL_HTML
    assert "Browser State" not in PANEL_HTML
    assert "function buildStateGraphData()" not in PANEL_HTML
    assert "function setupGraphModeToggle()" not in PANEL_HTML
    assert "function selectedGraphData()" in PANEL_HTML
    assert "return buildTrajectoryGraphData();" in PANEL_HTML


def test_panel_graph_has_view_controls_and_horizontal_bottom_legend():
    assert 'id="graph-controls" class="graph-controls"' in PANEL_HTML
    assert 'id="graph-fit" class="icon-only" type="button" aria-label="Show all graph nodes"' in PANEL_HTML
    assert 'id="graph-zoom-in" class="icon-only" type="button" aria-label="Zoom graph in"' in PANEL_HTML
    assert 'id="graph-zoom-out" class="icon-only" type="button" aria-label="Zoom graph out"' in PANEL_HTML
    assert "function fitToNodes()" in PANEL_HTML
    assert "function zoomBy(factor)" in PANEL_HTML
    assert "zoomBehavior.scaleBy" in PANEL_HTML
    assert "zoomBehavior.transform" in PANEL_HTML

    legend_css = PANEL_HTML.split(".graph-legend {", 1)[1].split(".graph-legend.hidden", 1)[0]
    assert "bottom: 14px;" in legend_css
    assert "right: 14px;" in legend_css
    assert "display: flex;" in legend_css
    assert "align-items: center;" in legend_css
    assert "top: 14px;" not in legend_css

    legend_bar_css = PANEL_HTML.split(".graph-legend .legend-bar {", 1)[1].split(
        ".graph-legend .legend-labels", 1
    )[0]
    assert "height: 10px;" in legend_bar_css
    assert "linear-gradient(90deg" in legend_bar_css


def test_panel_uses_action_artifacts_for_hierarchical_graph():
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]
    assert "recordBrowserStateGraph(ev.artifacts);" not in action_case
    assert "recordActionExecution(ev);" in action_case
    assert "function viewportInfoFromArtifacts(artifacts)" in PANEL_HTML
    assert "stateGraphLeaf(artifacts, 'viewport.size')" in PANEL_HTML
    assert "stateGraphLeaf(artifacts, 'viewport.scroll')" in PANEL_HTML



def test_panel_graph_supports_url_viewport_action_drilldown():
    assert "URL → viewport → action" in PANEL_HTML
    assert "Each level preserves chronological DAG edges" in PANEL_HTML
    assert "let graphDrilldown = { level: 'url', urlId: null, viewportId: null };" in PANEL_HTML
    assert "function buildUrlGraphData()" in PANEL_HTML
    assert "function buildViewportGraphData(urlId)" in PANEL_HTML
    assert "function buildActionGraphData(viewportId)" in PANEL_HTML
    assert "function buildSequentialLinks(sequence, allowedIds, rootId = null, allowSelfLoops = false)" in PANEL_HTML
    assert "function drillGraphNode(d)" in PANEL_HTML
    assert "setGraphDrilldown({ level: 'viewport', urlId: crumb.urlId, viewportId: null });" in PANEL_HTML
    assert 'id="graph-breadcrumb"' in PANEL_HTML


def test_panel_viewport_and_action_drilldowns_use_step_dag_edges():
    assert "viewportSequence: []" in PANEL_HTML
    assert "actionSequence: []" in PANEL_HTML
    assert "urlNode.viewportSequence.push(viewportId);" in PANEL_HTML
    assert "viewportNode.actionSequence.push(actionId);" in PANEL_HTML

    viewport_builder = PANEL_HTML.split("function buildViewportGraphData(urlId)", 1)[1].split(
        "function buildActionGraphData(viewportId)", 1
    )[0]
    assert "buildSequentialLinks(urlNode.viewportSequence, viewportIds, root.id)" in viewport_builder
    assert "viewports.map(vp => ({ source: root.id, target: vp.id" not in viewport_builder

    action_builder = PANEL_HTML.split("function buildActionGraphData(viewportId)", 1)[1].split(
        "function trajectoryLabelFor(n)", 1
    )[0]
    assert "buildSequentialLinks(viewportNode.actionSequence, actionIds, root.id, true)" in action_builder
    assert "actions.map(action => ({ source: root.id, target: action.id" not in action_builder


def test_panel_sequence_links_anchor_first_node_and_preserve_returns():
    link_builder = PANEL_HTML.split("function buildSequentialLinks(sequence, allowedIds, rootId = null, allowSelfLoops = false)", 1)[1].split(
        "function buildTrajectoryGraphData()", 1
    )[0]
    assert "let previous = rootId;" in link_builder
    assert "if (previous && (allowSelfLoops || previous !== id))" in link_builder
    assert "const edgeKey = `${previous}|${id}`;" in link_builder
    assert "if (edge) edge.count += 1;" in link_builder


def test_panel_uses_user_friendly_viewport_and_action_labels():
    assert "function scrollLabel(scroll)" in PANEL_HTML
    assert "function viewportLabel(viewport, stepId)" in PANEL_HTML
    assert "function actionLabel(actionName, args)" in PANEL_HTML
    assert "const stepLabel = stepId != null ? `Screen #${stepId}` : 'Screen view';" in PANEL_HTML
    assert "return `${stepLabel} · ${scrollLabel(viewport.scroll)}`;" in PANEL_HTML
    assert "label: viewportLabel(viewport, ev.step_id)" in PANEL_HTML
    assert "label: actionLabel(actionName, actionArgs)" in PANEL_HTML
    assert "if (actionName === 'click_at') return `Click at (${values.x}, ${values.y})`;" in PANEL_HTML
    assert "if (actionName === 'navigate') return `Open ${values.url || 'page'}`;" in PANEL_HTML
    assert "return String(actionName || 'Action').replace(/_/g, ' ');" in PANEL_HTML


def test_panel_action_graph_reuses_same_action_nodes_and_draws_cycles():
    assert "function stableActionValue(value)" in PANEL_HTML
    assert "function actionSignature(actionName, args)" in PANEL_HTML
    assert "const actionId = `action|${viewportId}|${actionSignature(actionName, actionArgs)}`;" in PANEL_HTML
    assert "let actionNode = trajectoryActions.get(actionId);" in PANEL_HTML
    assert "if (!actionNode)" in PANEL_HTML
    assert "actionNode.visits += 1;" in PANEL_HTML
    assert "viewportNode.actionSequence.push(actionId);" in PANEL_HTML
    assert "buildSequentialLinks(viewportNode.actionSequence, actionIds, root.id, true)" in PANEL_HTML
    assert "linkG.selectAll('path.graph-link')" in PANEL_HTML
    assert "function linkPath(d)" in PANEL_HTML
    assert "return `M ${sx} ${sy - 8} C" in PANEL_HTML
    assert "function detectCycleEdges(links)" in PANEL_HTML
    assert "const isCycleEdge = !!source && !!target && (source === target || (cyclicNodes.has(source) && cyclicNodes.has(target)));" in PANEL_HTML
    assert "detectCycleEdges(buildSequentialLinks(viewportNode.actionSequence, actionIds, root.id, true))" in PANEL_HTML
    assert ".classed('cycle', d => !!d.isCycleEdge)" in PANEL_HTML
    assert ".graph-link.cycle" in PANEL_HTML
    assert 'id="graph-arrow-cycle"' in PANEL_HTML


def test_panel_graph_action_artifacts_prioritize_replay_and_compare_controls():
    assert "function renderActionReplayCard(label, href)" in PANEL_HTML
    assert "function renderBeforeAfterCompare(beforeHref, afterHref)" in PANEL_HTML
    assert "class=\"artifact-primary\"" in PANEL_HTML
    assert "class=\"artifact-compare-tabs\"" in PANEL_HTML
    assert "data-compare-mode=\"before\"" in PANEL_HTML
    assert "data-compare-mode=\"after\"" in PANEL_HTML
    assert "data-compare-mode=\"split\"" in PANEL_HTML
    assert "class=\"artifact-split\"" in PANEL_HTML
    assert "Technical paths" in PANEL_HTML


def test_panel_graph_action_artifacts_do_not_render_flat_three_card_compare():
    artifact_renderer = PANEL_HTML.split("function renderActionArtifacts(artifacts)", 1)[1].split(
        "function actionPreviewArtifactsFor(action)", 1
    )[0]
    assert "renderArtifactCard('action GIF', actionGif)" not in artifact_renderer
    assert "renderArtifactCard('before', beforeShot)" not in artifact_renderer
    assert "renderArtifactCard('after', afterShot)" not in artifact_renderer


def test_panel_graph_selection_can_show_llm_raw_context_and_response():
    assert "let llmInferencesByStep = new Map();" in PANEL_HTML
    assert "case 'llm_inference':" in PANEL_HTML
    assert "storeLlmInference(ev);" in PANEL_HTML
    assert "window.getLlmInferenceForStep = getLlmInferenceForStep;" in PANEL_HTML
    assert "function renderLlmInferenceButton(inference)" in PANEL_HTML
    assert "View LLM raw context / response" in PANEL_HTML
    assert "Raw context" in PANEL_HTML
    assert "Output response" in PANEL_HTML
    assert "llmInference: llmInferenceForStep(ev.step_id)" in PANEL_HTML
    assert "renderLlmInferenceButton(d.llmInference)" in PANEL_HTML
    assert ".llm-raw-details" in PANEL_HTML


def test_panel_removes_browser_state_tree_rendering():
    assert "no BrowserState graph metadata yet." not in PANEL_HTML
    assert ".graph-node.group circle" not in PANEL_HTML
    assert ".graph-node.leaf circle" not in PANEL_HTML
    assert ".graph-node.changed circle" not in PANEL_HTML
    assert "function treeDrag()" not in PANEL_HTML
    assert "function positionTreeLinks()" not in PANEL_HTML


def test_panel_has_replay_session_controls():
    assert 'id="sessions-btn"' in PANEL_HTML
    assert 'id="sessions-panel"' in PANEL_HTML
    assert 'id="replay-controls"' in PANEL_HTML


def test_panel_run_button_toggles_to_stop_and_status_uses_loading_indicator():
    assert 'id="btn"' in PANEL_HTML
    assert 'id="btn-icon-path"' in PANEL_HTML
    assert 'id="stop-btn"' not in PANEL_HTML
    assert 'id="run-loading"' not in PANEL_HTML
    assert 'id="status-loading"' in PANEL_HTML
    assert '@keyframes m3-loading-morph' in PANEL_HTML
    assert '.status-dot.running      { display: none; }' in PANEL_HTML
    assert "statusLoading.classList.toggle('active', state === 'running');" in PANEL_HTML
    assert "fetch('/interrupt', { method: 'POST' })" in PANEL_HTML
    assert "case 'task_interrupted':" in PANEL_HTML
    assert "btn.classList.toggle('stop', stopMode);" in PANEL_HTML
    assert "btnIconPath.setAttribute('d', stopMode ? 'M6 6h12v12H6z' : 'M8 5v14l11-7z');" in PANEL_HTML
    assert "if (isRunning || isSubmitting)" in PANEL_HTML
    assert 'id="replay-slider"' in PANEL_HTML
    assert 'function loadSessions()' in PANEL_HTML
    assert 'async function startReplay(sessionId)' in PANEL_HTML


def test_panel_start_replay_renders_loaded_session_immediately_and_reports_failures():
    start_replay = PANEL_HTML.split("async function startReplay(sessionId)", 1)[1].split(
        "sessionsBtn.addEventListener", 1
    )[0]

    assert "function showReplayMessage(title, detail, cls = 'red')" in PANEL_HTML
    assert "replayTo(replayEvents.length);" in start_replay
    assert "showReplayMessage('No replay events.'" in start_replay
    assert "showReplayMessage('Could not load replay session'" in start_replay
    assert "if (!res.ok) throw new Error(`HTTP ${res.status}`);" in start_replay


def test_panel_disables_live_input_and_ignores_ws_during_replay():
    assert "if (replayMode) return;" in PANEL_HTML
    assert "function setReplayUi(active)" in PANEL_HTML
    assert "setInputEnabled(!active && !isRunning" in PANEL_HTML
    assert "setStatus('connected', 'replay')" in PANEL_HTML


def test_panel_links_replay_screenshots_from_action_artifacts():
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]
    assert "storeArtifactsForStep(ev.step_id, ev.artifacts);" in action_case
    timeline_render = PANEL_HTML.split("function renderTimelineActionStepInfo(stepId)", 1)[1].split(
        "function refreshAdditionalInfoForStep", 1
    )[0]
    assert "renderActionArtifacts(artifacts)" in timeline_render


def test_panel_uses_apple_design_theme_tokens():
    assert '"SF Pro Text"' in PANEL_HTML
    assert '"SF Pro Display"' in PANEL_HTML
    # Material Design system tokens remain the internal implementation surface.
    assert "--md-sys-color-primary:" in PANEL_HTML
    assert "--md-sys-color-on-primary:" in PANEL_HTML
    assert "--md-sys-color-surface-container:" in PANEL_HTML
    # M3 shape + elevation scales
    assert "--md-sys-shape-corner-lg:" in PANEL_HTML
    assert "--md-sys-elevation-3:" in PANEL_HTML
    # Legacy aliases preserved for in-file references
    assert "--primary:" in PANEL_HTML
    assert "--surface-1:" in PANEL_HTML
    assert "--radius-lg:" in PANEL_HTML
    assert "--shadow-2:" in PANEL_HTML


def test_panel_uses_original_m3_light_palette():
    assert "--md-sys-color-primary:                #0b57d0;" in PANEL_HTML
    assert "--md-sys-color-background:             #f8fafd;" in PANEL_HTML
    assert "--md-sys-color-on-surface:             #1a1c1e;" in PANEL_HTML
    assert "--md-sys-color-outline:                #74777f;" in PANEL_HTML
    assert "--app-bg-radial-1: rgba(11, 87, 208, 0.12);" in PANEL_HTML
    assert "radial-gradient(circle at 12% 10%, var(--app-bg-radial-1), transparent 28rem)" in PANEL_HTML


def test_panel_supports_original_m3_dark_theme_tokens():
    assert 'html[data-theme="dark"]' in PANEL_HTML
    assert "color-scheme: dark;" in PANEL_HTML
    assert "--md-sys-color-primary:                #a8c7fa;" in PANEL_HTML
    assert "--md-sys-color-background:             #111418;" in PANEL_HTML
    assert "--md-sys-color-on-surface:             #e2e2e9;" in PANEL_HTML
    assert "--app-bg-radial-1: rgba(168, 199, 250, 0.16);" in PANEL_HTML
    assert "0 4px 8px 3px rgba(0,0,0,.15)," in PANEL_HTML
    assert "no dark-mode override" not in PANEL_HTML


def test_panel_uses_more_compact_corner_radius_scale():
    assert "--md-sys-shape-corner-sm:    6px;" in PANEL_HTML
    assert "--md-sys-shape-corner-md:    8px;" in PANEL_HTML
    assert "--md-sys-shape-corner-lg:   12px;" in PANEL_HTML
    assert "--md-sys-shape-corner-xl:   16px;" in PANEL_HTML
    assert "--md-sys-shape-corner-xl:   28px;" not in PANEL_HTML


def test_panel_has_accessible_theme_toggle():
    assert 'id="theme-toggle" class="icon-only" type="button"' in PANEL_HTML
    assert 'aria-label="Switch to dark theme"' in PANEL_HTML
    assert 'aria-pressed="false"' in PANEL_HTML
    assert 'title="Switch to dark theme"' in PANEL_HTML
    assert 'id="theme-toggle-path"' in PANEL_HTML
    assert "const themeToggle = document.getElementById('theme-toggle');" in PANEL_HTML
    assert "themeToggle.setAttribute('aria-pressed', String(isDark));" in PANEL_HTML


def test_panel_theme_uses_system_default_and_persists_user_choice():
    assert 'const THEME_STORAGE_KEY = "bragent.theme";' in PANEL_HTML
    assert 'localStorage.getItem(THEME_STORAGE_KEY)' in PANEL_HTML
    assert 'localStorage.setItem(THEME_STORAGE_KEY, next)' in PANEL_HTML
    assert 'window.matchMedia("(prefers-color-scheme: dark)")' in PANEL_HTML
    assert "media.addEventListener('change', syncSystemTheme)" in PANEL_HTML
    assert "document.documentElement.dataset.theme = theme;" in PANEL_HTML
    assert "document.documentElement.style.colorScheme = theme;" in PANEL_HTML


def test_panel_primary_run_button_uses_material_icon_button_style():
    assert "#btn {" in PANEL_HTML
    # M3 Filled Button uses sys color tokens directly
    assert "background: var(--md-sys-color-primary);" in PANEL_HTML
    assert "color: var(--md-sys-color-on-primary);" in PANEL_HTML
    assert 'aria-label="Run task"' in PANEL_HTML
    assert 'title="Run task"' in PANEL_HTML
    assert '<button id="btn" class="icon-only" type="button" aria-label="Run task" title="Run task" disabled>' in PANEL_HTML
    assert "<svg class=\"btn-icon\" aria-hidden=\"true\" viewBox=\"0 0 24 24\" focusable=\"false\">" in PANEL_HTML
    assert '<path id="btn-icon-path" d="M8 5v14l11-7z"></path>' in PANEL_HTML
    button_css = PANEL_HTML.split("#btn {", 1)[1].split("#btn .btn-icon", 1)[0]
    assert "width: 36px;" in button_css
    assert "min-width: 36px;" in button_css
    assert "height: 36px;" in button_css
    assert "padding: 0;" in PANEL_HTML
    assert "<button id=\"btn\" type=\"button\" disabled>run</button>" not in PANEL_HTML




def test_panel_header_controls_use_shared_header_order():
    header_html = PANEL_HTML.split("<header>", 1)[1].split("</header>", 1)[0]

    live_idx = header_html.index('id="live-btn"')
    sessions_idx = header_html.index('id="sessions-btn"')
    theme_idx = header_html.index('id="theme-toggle"')

    assert live_idx < sessions_idx < theme_idx
    assert '"header       header       header  header        header"' in PANEL_HTML
    assert 'class="sheet-header"' not in PANEL_HTML

def test_panel_secondary_controls_use_svg_icons_with_accessible_labels():
    assert 'id="sessions-btn" class="icon-label" type="button" aria-label="Open history"' in PANEL_HTML
    assert '<span>History</span>' in PANEL_HTML
    assert 'id="live-btn" class="icon-label" type="button" aria-label="Start new live view"' in PANEL_HTML
    assert '<span>New</span>' in PANEL_HTML
    assert '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"></path>' in PANEL_HTML
    assert 'id="sessions-close" class="icon-only" type="button" aria-label="Close saved sessions"' in PANEL_HTML
    assert 'id="replay-prev" class="icon-only" type="button" aria-label="Previous replay step"' in PANEL_HTML
    assert 'id="replay-play" class="icon-only" type="button" aria-label="Play or pause replay"' in PANEL_HTML
    assert 'id="replay-next" class="icon-only" type="button" aria-label="Next replay step"' in PANEL_HTML
    assert 'class="view-tab icon-label active" data-view="timeline"' in PANEL_HTML
    assert 'class="view-tab icon-label" data-view="graph"' in PANEL_HTML
    assert 'btn.className = \'session-item icon-label\';' in PANEL_HTML
    assert "<button id=\"sessions-close\" type=\"button\">×</button>" not in PANEL_HTML
    assert "<button id=\"replay-prev\" type=\"button\">⏮</button>" not in PANEL_HTML
    assert "<button id=\"replay-play\" type=\"button\">⏯</button>" not in PANEL_HTML
    assert "<button id=\"replay-next\" type=\"button\">⏭</button>" not in PANEL_HTML
    assert "`▶ ${escHtml(session.id)}" not in PANEL_HTML


def test_panel_left_sidebar_always_shows_task_status_and_plan():
    left_html = PANEL_HTML_ONLY.split('<aside id="left-sidebar"', 1)[1].split("</aside>", 1)[0]
    right_html = PANEL_HTML_ONLY.split('<aside id="right-sidebar"', 1)[1].split("</aside>", 1)[0]

    assert '<aside id="left-sidebar" class="side-panel" aria-label="Session details">' in PANEL_HTML_ONLY
    assert '<aside id="right-sidebar" class="side-panel" aria-label="Additional action information">' in PANEL_HTML_ONLY
    assert 'class="side-section side-scroll-section side-task-section"' in PANEL_HTML
    assert 'class="side-section side-scroll-section side-plan-section"' in PANEL_HTML
    assert '<summary data-icon="task_alt">Task</summary>' in left_html
    assert '<summary data-icon="monitor_heart">Status</summary>' in left_html
    assert '<summary data-icon="route">Plan</summary>' in left_html
    assert '<summary data-icon="ads_click">Additional Info</summary>' in right_html
    assert "data-side-view" not in PANEL_HTML_ONLY
    assert 'class="side-section side-scroll-section side-activity-section"' not in PANEL_HTML
    assert 'id="side-activity"' not in PANEL_HTML
    assert "details.side-scroll-section[open]" in PANEL_HTML
    assert "details.side-scroll-section > .side-body" not in PANEL_HTML


def test_panel_plan_status_uses_icons_instead_of_text_markers():
    render_plan = PANEL_HTML.split("function renderPlan()", 1)[1].split(
        "function upsertActionSummary", 1
    )[0]

    assert "const statusIcons = {" in render_plan
    assert '<span class="status-icon">' in render_plan
    assert "<svg aria-hidden=\"true\"" in render_plan
    for marker in ("[ ]", "[›]", "[✓]", "[✗]"):
        assert marker not in render_plan


def test_panel_graph_pins_root_nodes_and_seeds_children_from_parent():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function updateGraph()", 1
    )[0]

    assert "function rootPosition(" in graph_renderer
    assert "function arrangeGraphNodes(" in graph_renderer
    assert "x: graphMode === 'url' ? (index - (count - 1) / 2) * 140 : 0," in graph_renderer
    assert "y: graphMode === 'url' ? -180 : -220," in graph_renderer
    assert "node.fx = pinned.x;" in graph_renderer
    assert "node.fy = pinned.y;" in graph_renderer
    assert "node.x = baseX + offsetX;" in graph_renderer
    assert "node.y = baseY + 150;" in graph_renderer
    assert "return d && d.isRoot ? rootPosition().y : 90;" in graph_renderer
    assert "simulation.force('x').x(d => targetX(d));" in graph_renderer
    assert "simulation.force('y').y(d => targetY(d));" in graph_renderer
    assert "if (d.isRoot) {" in graph_renderer


def test_panel_graph_clears_stale_root_flag_when_reusing_nodes():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function updateGraph()", 1
    )[0]

    assert "function normalizeGraphNode(src)" in graph_renderer
    assert "isRoot: false," in graph_renderer
    assert "return Object.assign(prev || {}, normalizeGraphNode(src));" in graph_renderer
    assert "return Object.assign(prev || {}, src);" not in graph_renderer


def test_panel_cards_use_symmetric_compact_divider_gap():
    main_css = PANEL_HTML.split("main#main {", 2)[2].split("}", 1)[0]
    left_sidebar_css = PANEL_HTML.split("aside#left-sidebar {", 1)[1].split("}", 1)[0]
    right_sidebar_css = PANEL_HTML.split("aside#right-sidebar {", 1)[1].split("}", 1)[0]
    footer_css = PANEL_HTML.split("\n  footer {", 1)[1].split("}", 1)[0]

    assert "margin: 16px 8px 12px;" in main_css
    assert "margin: 16px 8px 16px 12px;" in left_sidebar_css
    assert "margin: 16px 12px 16px 8px;" in right_sidebar_css
    assert "padding: 4px 8px 16px;" in footer_css


def test_panel_resizers_use_short_rounded_rect_handles():
    resizer_css = PANEL_HTML.split(".resizer::before {", 1)[1].split("}", 1)[0]
    resizer_hover_css = PANEL_HTML.split("body.resizing .resizer.active::before {", 1)[1].split("}", 1)[0]

    assert "grid-template-columns: var(--left-aside-w) 8px minmax(0, 1fr) 8px var(--right-aside-w);" in PANEL_HTML
    assert 'id="left-resizer" class="resizer"' in PANEL_HTML
    assert 'id="right-resizer" class="resizer"' in PANEL_HTML
    assert "left: 50%;" in resizer_css
    assert "top: 50%;" in resizer_css
    assert "width: 4px;" in resizer_css
    assert "height: 44px;" in resizer_css
    assert "transform: translate(-50%, -50%);" in resizer_css
    assert "bottom: 14px;" not in resizer_css
    assert "height: 56px;" in resizer_hover_css
    assert "var(--primary)" not in resizer_hover_css


def test_panel_chatbox_has_all_corners_rounded():
    input_shell_css = PANEL_HTML.split(".input-shell {", 1)[1].split("}", 1)[0]

    assert "border-radius: var(--md-sys-shape-corner-xl);" in input_shell_css
    assert "background: var(--md-sys-color-surface-container-highest);" in input_shell_css
    assert "linear-gradient(180deg" not in input_shell_css
    assert "border-bottom" not in input_shell_css
    assert ".input-shell:focus-within" not in PANEL_HTML


def test_panel_sidebar_itself_is_viewport_constrained_and_scrollable():
    sidebar_css = PANEL_HTML.split("aside.side-panel {", 1)[1].split("}", 1)[0]
    sheet_body_css = PANEL_HTML.split(".sheet-body {", 1)[1].split("}", 1)[0]
    side_section_css = PANEL_HTML.split("details.side-section {", 1)[1].split("}", 1)[0]
    side_scroll_css = PANEL_HTML.split("details.side-scroll-section[open] {", 1)[1].split("}", 1)[0]
    task_section_css = PANEL_HTML.split("details.side-task-section[open] {", 1)[1].split("}", 1)[0]

    # The sidebar shares the top app bar, so only the body row scrolls under it.
    assert "display: grid;" in sidebar_css
    assert "grid-template-rows: minmax(0, 1fr);" in sidebar_css
    assert "height: 100dvh;" not in sidebar_css
    assert "max-height: 100dvh;" not in sidebar_css
    assert "align-self: stretch;" in sidebar_css
    assert "border-radius: var(--md-sys-shape-corner-xl);" in sidebar_css
    assert "border-radius: var(--md-sys-shape-corner-lg) 0 0 var(--md-sys-shape-corner-lg);" not in sidebar_css
    assert 'class="sheet-header"' not in PANEL_HTML
    assert 'id="side-title"' not in PANEL_HTML
    # The scrollable region is the sheet-body, not the aside itself.
    assert "overflow-y: auto;" in sheet_body_css
    assert "overscroll-behavior: contain;" in sheet_body_css
    assert "scrollbar-gutter: stable;" in sheet_body_css
    assert "overflow: visible;" in side_section_css
    assert "display: grid;" in PANEL_HTML.split("details.side-section[open] {", 1)[1].split("}", 1)[0]
    assert "grid-template-rows: auto minmax(0, auto);" in PANEL_HTML
    assert "max-height: none;" in task_section_css


def test_panel_sidebar_long_content_uses_flow_safe_grid_items():
    side_section_css = PANEL_HTML.split("details.side-section {", 1)[1].split("}", 1)[0]
    side_body_css = PANEL_HTML.split(".side-body {", 1)[1].split("}", 1)[0]
    todo_css = PANEL_HTML.split(".todo {", 1)[1].split("}", 1)[0]
    action_summary_css = PANEL_HTML.split(".action-summary-card .summary-head {", 1)[1].split("}", 1)[0]

    assert "position: relative;" in side_section_css
    assert "flex: 0 0 auto;" in side_section_css
    assert "width: 100%;" in side_section_css
    assert "min-width: 0;" in side_body_css
    assert "max-width: 100%;" in side_body_css
    assert "word-break: break-word;" in side_body_css
    assert "grid-template-columns: 30px minmax(0, 1fr);" in todo_css
    assert "display: flex;" in action_summary_css
    assert "align-items: flex-start;" in action_summary_css
    assert ".todo .text  { color: var(--fg); min-width: 0; overflow-wrap: anywhere; }" in PANEL_HTML
    assert "min-width: 0;" in PANEL_HTML.split(".action-summary-card .summary-copy {", 1)[1].split("}", 1)[0]
    assert "overflow-wrap: anywhere;" in PANEL_HTML.split(".action-summary-card .summary-copy {", 1)[1].split("}", 1)[0]


def test_panel_sidebar_toggle_uses_material_arrow_drop_down_icon():
    toggle_css = PANEL_HTML.split("details.side-section > summary::after {", 1)[1].split("}", 1)[0]
    open_toggle_css = PANEL_HTML.split("details.side-section[open] > summary::after {", 1)[1].split("}", 1)[0]

    assert "Material+Symbols+Rounded" in PANEL_HTML
    assert 'content: "arrow_drop_down";' in toggle_css
    assert 'font-family: "Material Symbols Rounded";' in toggle_css
    assert 'font-feature-settings: "liga";' in toggle_css
    assert "transform: rotate(-90deg);" in toggle_css
    assert "transform: rotate(0deg);" in open_toggle_css
    assert "linear-gradient(45deg" not in toggle_css


def test_panel_sidebar_sections_use_material_list_item_icons():
    before_css = PANEL_HTML.split("details.side-section > summary::before {", 1)[1].split("}", 1)[0]

    assert 'content: attr(data-icon);' in before_css
    assert 'font-family: "Material Symbols Rounded";' in before_css
    assert '<summary data-icon="task_alt">Task</summary>' in PANEL_HTML
    assert '<summary data-icon="monitor_heart">Status</summary>' in PANEL_HTML
    assert '<summary data-icon="route">Plan</summary>' in PANEL_HTML
    assert '<summary data-icon="history">Activity</summary>' not in PANEL_HTML


def test_panel_empty_state_uses_material_symbol_illustration():
    empty_icon_css = PANEL_HTML.split("#empty-state::before {", 1)[1].split("}", 1)[0]

    assert 'content: "travel_explore";' in empty_icon_css
    assert 'font-family: "Material Symbols Rounded";' in empty_icon_css
    assert "border-radius: var(--md-sys-shape-corner-xl);" in empty_icon_css


def test_panel_step_complete_does_not_render_extra_timeline_summary():
    step_complete_case = PANEL_HTML.split("case 'step_complete':", 1)[1].split(
        "case 'task_complete':", 1
    )[0]
    summary_css = PANEL_HTML.split(".action-summary-card {", 1)[1].split("}", 1)[0]
    summary_hover_css = PANEL_HTML.split(".action-summary-card:hover {", 1)[1].split("}", 1)[0]

    assert "addBlock('plain'," not in step_complete_case
    assert "step complete" not in step_complete_case
    assert "addBlock('green'," not in step_complete_case
    assert "border-left" not in summary_css
    assert "--phase-border" not in summary_css
    assert "--phase-bg" not in summary_css
    assert "--phase-bg" not in summary_hover_css


def test_panel_action_summaries_render_clickable_timeline_cards_without_inline_details():
    review_case = PANEL_HTML.split("case 'review_metadata_extracted':", 1)[1].split(
        "case 'action_executed':", 1
    )[0]

    assert "function upsertActionSummary(item)" in PANEL_HTML
    assert "function renderActionSummaryCard(card, item)" in PANEL_HTML
    assert "currentTimelineStepGroup.appendChild(card);" in PANEL_HTML
    assert "upsertActionSummary({" in review_case
    assert "addActivity({" not in review_case
    assert '<div role="button" tabindex="0" class="action-summary-card"' in PANEL_HTML
    assert "selectTimelineActionStep(key);" in PANEL_HTML
    assert "Action summary details" not in PANEL_HTML


def test_panel_right_additional_info_includes_reasoning_artifacts_and_llm_button():
    assert "let reasoningByStep = new Map();" in PANEL_HTML
    assert "storeStepReasoning(ev.step_id, ev.reasoning);" in PANEL_HTML
    assert "refreshAdditionalInfoForStep(stepId);" in PANEL_HTML
    assert "Reasoning" in PANEL_HTML
    timeline_render = PANEL_HTML.split("function renderTimelineActionStepInfo(stepId)", 1)[1].split(
        "function refreshAdditionalInfoForStep", 1
    )[0]
    assert "renderActionArtifacts(artifacts)" in timeline_render
    assert "renderLlmInferenceButton(inference)" in timeline_render
    assert "let artifactsByStep = new Map();" in PANEL_HTML
    assert "storeArtifactsForStep(ev.step_id, ev.artifacts);" in PANEL_HTML


def test_panel_agent_step_raw_events_are_hidden_behind_action_summary_details():
    reasoning_case = PANEL_HTML.split("case 'reasoning_extracted':", 1)[1].split(
        "case 'function_calls_extracted':", 1
    )[0]
    calls_case = PANEL_HTML.split("case 'function_calls_extracted':", 1)[1].split(
        "case 'review_metadata_extracted':", 1
    )[0]
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]

    assert "addRow('thinking'" not in reasoning_case
    assert "storeFunctionCalls(ev.step_id, calls);" in calls_case
    assert "addRow('', `<span style=\"color:var(--fg-dim)\">⚙" not in calls_case
    assert "storeObservedUrl(ev.step_id, ev.env_state.url);" in action_case
    assert "addRow('dim', `@ <span class=\"url\">" not in action_case
    assert "Function calls" in PANEL_HTML
    assert "Observed URL" in PANEL_HTML


def test_panel_user_chat_messages_are_right_aligned():
    task_started_case = PANEL_HTML.split("case 'task_started':", 1)[1].split(
        "case 'planner_started':", 1
    )[0]
    step_started_case = PANEL_HTML.split("case 'step_started':", 1)[1].split(
        "case 'llm_inference':", 1
    )[0]

    assert "addSpeaker('user', null);" in task_started_case
    assert "addRow('user-message', escHtml(ev.query));" in task_started_case
    assert "addSpeaker('browser-agent', null);" in task_started_case
    assert "addSpeaker('browser-agent', `step ${ev.step_id}`);" not in step_started_case
    assert "addSpeaker('browser-agent'" not in step_started_case
    assert "el.className = `speaker ${name === 'user' ? 'user-speaker' : 'agent-speaker'}`;" in PANEL_HTML
    assert ".row.user-message" in PANEL_HTML
    assert "align-self: flex-end;" in PANEL_HTML
    assert ".speaker.user-speaker" in PANEL_HTML


def test_panel_removes_keybind_help_bar():
    assert 'class="keybind"' not in PANEL_HTML
    assert "enter</kbd> submit" not in PANEL_HTML
    assert "shift+enter</kbd> newline" not in PANEL_HTML
    assert "esc</kbd> interrupt" not in PANEL_HTML
    assert '"keybind resizer aside"' not in PANEL_HTML
    assert '"header       header       header  header        header"' in PANEL_HTML
    assert 'grid-template-areas: "header" "main" "footer";' in PANEL_HTML


def test_panel_graph_selection_renders_action_before_after_artifacts():
    assert "function renderActionArtifacts(artifacts)" in PANEL_HTML
    assert "function replayArtifactHref(path, expectedDir = 'history')" in PANEL_HTML
    assert "beforeScreenshotPath: ev.artifacts && ev.artifacts.before_screenshot_path" in PANEL_HTML
    assert "afterScreenshotPath: ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path)" in PANEL_HTML
    assert "actionGifPath: ev.artifacts && (ev.artifacts.action_clip_gif_path || ev.artifacts.action_gif_path)" in PANEL_HTML
    assert "videoPath: ev.artifacts && ev.artifacts.video_path" in PANEL_HTML
    assert "renderActionReplayCard('Action replay', actionGif)" in PANEL_HTML
    assert "renderBeforeAfterCompare(beforeShot, afterShot)" in PANEL_HTML
    assert "renderArtifactCard('session video', video, 'video')" in PANEL_HTML
    assert "renderActionArtifacts(d.artifacts)" in PANEL_HTML


def test_panel_graph_and_timeline_selection_share_action_step_highlight_and_info():
    assert ".action-step-group.timeline-highlight" in PANEL_HTML
    assert "function beginActionStepGroup(stepId)" in PANEL_HTML
    assert "currentTimelineStepGroup.dataset.stepId = String(stepId);" in PANEL_HTML
    assert "currentTimelineStepGroup.addEventListener('click'" in PANEL_HTML
    assert "function selectTimelineActionStep(stepId)" in PANEL_HTML
    assert "renderTimelineActionStepInfo(selectedTimelineStepId);" in PANEL_HTML
    assert "function highlightTimelineActionStep(stepId)" in PANEL_HTML
    assert "function timelineStepForGraphNode(d)" in PANEL_HTML
    assert "highlightTimelineActionStep(timelineStepForGraphNode(selectedNodeData));" in PANEL_HTML
    assert "highlightTimelineActionStep(null);" in PANEL_HTML
    assert "appendTimelineElement(el);" in PANEL_HTML
    assert "if (currentTimelineStepGroup) currentTimelineStepGroup.appendChild(el);" in PANEL_HTML


def test_panel_graph_separates_selected_and_running_node_accents():
    assert "let activeGraphStepId = null;" in PANEL_HTML
    assert "let trajectoryCurrentViewportId = null;" in PANEL_HTML
    assert "let trajectoryCurrentActionId = null;" in PANEL_HTML
    assert "function isRunningGraphNode(d)" in PANEL_HTML
    assert ".graph-node.selected circle" in PANEL_HTML
    assert ".graph-node.current circle" in PANEL_HTML
    assert ".graph-node.running circle" in PANEL_HTML
    assert "trajectoryCurrentViewportId = viewportId;" in PANEL_HTML
    assert "trajectoryCurrentActionId = actionId;" in PANEL_HTML
    assert "isCurrent: vp.id === trajectoryCurrentViewportId" in PANEL_HTML
    assert "isCurrent: action.id === trajectoryCurrentActionId" in PANEL_HTML
    assert ".classed('current', d => !!d.isCurrent)" in PANEL_HTML
    assert ".classed('running', d => isRunningGraphNode(d))" in PANEL_HTML
    assert ".classed('selected', d => d.id === selectedNodeId)" in PANEL_HTML
    assert ".classed('current', d => d.isCurrent)" not in PANEL_HTML
    assert "activeGraphStepId = stepId != null ? String(stepId) : null;" in PANEL_HTML
    assert "function refreshRunning()" in PANEL_HTML
    assert "return { update, reset, resize, refreshSelection, refreshRunning };" in PANEL_HTML
    assert "updateGraphRunningClass();" in PANEL_HTML


def test_panel_graph_uses_opaque_plotly_viridis_work_color_scale():
    assert "fill: var(--graph-node-fill, var(--surface-2));" in PANEL_HTML
    assert "function graphNodeWorkCount(d)" in PANEL_HTML
    assert "if (Number.isFinite(d.actionCount)) return d.actionCount;" in PANEL_HTML
    assert "function graphNodeFill(d, maxWorkCount)" in PANEL_HTML
    assert "d3.interpolateViridis(0.12)" in PANEL_HTML
    assert "d3.interpolateViridis(t)" in PANEL_HTML
    assert "d3.interpolateBlues" not in PANEL_HTML
    assert "const maxWorkCount = Math.max(1, ...nodesData.map(graphNodeWorkCount));" in PANEL_HTML
    assert ".style('--graph-node-fill', d => graphNodeFill(d, maxWorkCount));" in PANEL_HTML
    assert "stroke: transparent;" in PANEL_HTML
    assert "stroke-width: 0;" in PANEL_HTML
    assert ".graph-node.viewport circle { stroke:" not in PANEL_HTML
    assert ".graph-node.action circle { stroke:" not in PANEL_HTML
    assert "rgba(253, 214, 99, 0.12)" not in PANEL_HTML
    assert "rgba(129, 201, 149, 0.12)" not in PANEL_HTML


def test_panel_current_node_accent_preserves_work_fill():
    current_rule = PANEL_HTML.split(".graph-node.current circle {", 1)[1].split("}", 1)[0]
    assert "stroke: var(--md-sys-color-tertiary);" in current_rule
    assert "stroke-width: 3;" in current_rule
    assert "fill:" not in current_rule
    assert "filter:" not in current_rule


def test_panel_graph_base_nodes_hide_stroke_until_accented():
    base_rule = PANEL_HTML.split(".graph-node circle {", 1)[1].split("}", 1)[0]
    assert "stroke: transparent;" in base_rule
    assert "stroke-width: 0;" in base_rule
    assert "stroke-width 0.16s ease" in base_rule
    assert ".graph-node.root circle" not in PANEL_HTML
    assert ".graph-node.url circle" not in PANEL_HTML
    assert ".graph-node.viewport circle" not in PANEL_HTML
    assert ".graph-node.action circle" not in PANEL_HTML
    for accent in (".graph-node.current circle", ".graph-node.running circle", ".graph-node.selected circle"):
        rule = PANEL_HTML.split(accent + " {", 1)[1].split("}", 1)[0]
        assert "stroke:" in rule
        assert "stroke-width: 3;" in rule
        assert "fill:" not in rule
        assert "filter:" not in rule


def test_panel_graph_shows_work_color_legend():
    assert 'id="graph-legend"' in PANEL_HTML
    assert 'aria-label="Node color legend"' in PANEL_HTML
    assert "work count" not in PANEL_HTML
    assert "legend-title" not in PANEL_HTML
    assert "data-legend-max" in PANEL_HTML
    legend_css = PANEL_HTML.split(".graph-legend {", 1)[1].split(".graph-legend.hidden", 1)[0]
    assert "bottom: 14px;" in legend_css
    assert "right: 14px;" in legend_css
    assert "top: 14px;" not in legend_css
    assert "background: linear-gradient(90deg, #482878 0%, #3e4989 25%, #26828e 50%, #35b779 75%, #fde725 100%);" in PANEL_HTML
    assert "flex-direction: row;" in PANEL_HTML
    assert "flex-direction: column-reverse;" not in PANEL_HTML
    assert "const legendEl = document.getElementById('graph-legend');" in PANEL_HTML
    assert "function updateGraphLegend(maxWorkCount, hasNodes)" in PANEL_HTML
    assert "maxLabel.textContent = `max ${maxWorkCount}`;" in PANEL_HTML
    assert "updateGraphLegend(maxWorkCount, nodesData.length > 0);" in PANEL_HTML
    assert "updateGraphLegend(1, false);" in PANEL_HTML


def test_panel_graph_hover_tooltip_stays_compact():
    tooltip_block = PANEL_HTML.split("function showTooltip(event, d) {", 1)[1].split("function moveTooltip(event)", 1)[0]
    assert "const title = d.label || d.host || d.actionName || d.id;" in tooltip_block
    assert "<span>level</span>" in tooltip_block
    assert "<span>actions</span>" in tooltip_block
    assert "<span>visits</span>" in tooltip_block
    assert "drill in" in tooltip_block
    for hidden_detail in ("<span>host</span>", "<span>path</span>", "<span>size</span>", "<span>scroll</span>", "<span>shot</span>", "<span>args</span>", "<span>first step</span>", "<span>last step</span>", "<span>out / in</span>", "<span>click</span>"):
        assert hidden_detail not in tooltip_block


def test_panel_uses_live_session_id_for_graph_artifacts_outside_replay():
    task_started_case = PANEL_HTML.split("case 'task_started':", 1)[1].split(
        "case 'planner_started':", 1
    )[0]
    replay_href = PANEL_HTML.split("function replayArtifactHref(path, expectedDir = 'history')", 1)[1].split(
        "function renderArtifactCard", 1
    )[0]

    assert "let liveSessionId = null;" in PANEL_HTML
    assert "liveSessionId = ev.session_id || null;" in task_started_case
    assert "const sessionId = replayMode ? replaySessionId : liveSessionId;" in replay_href
    assert "if (!sessionId || !path) return '';" in replay_href


def test_panel_aggregates_child_action_gif_previews_for_url_and_viewport_nodes():
    assert "function collectActionPreviewArtifacts(actionIds)" in PANEL_HTML
    assert "artifacts.action_clip_gif_path || artifacts.action_gif_path || artifacts.after_screenshot_path || artifacts.screenshot_path" in PANEL_HTML
    assert "actionPreviews: collectActionPreviewArtifacts(src.actionIds)" in PANEL_HTML
    assert "actionPreviews: collectActionPreviewArtifacts(vp.actionIds)" in PANEL_HTML
    assert "renderActionPreviewGallery(d.actionPreviews)" in PANEL_HTML
    assert "child previews" in PANEL_HTML
    assert ".artifact-gallery" in PANEL_HTML


def test_panel_prefers_action_clip_gif_over_two_frame_fallback():
    assert "artifacts.action_clip_gif_path || artifacts.action_gif_path" in PANEL_HTML
    assert "action_clip_gif_path" in PANEL_HTML
