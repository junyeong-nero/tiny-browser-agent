import re
from pathlib import Path

from fastapi.testclient import TestClient

from ui.server import app


PANEL_HTML_ONLY = Path("src/ui/panel.html").read_text(encoding="utf-8")
PANEL_CSS = Path("src/ui/static/panel.css").read_text(encoding="utf-8")
PANEL_JS = Path("src/ui/static/panel.js").read_text(encoding="utf-8")
_GRAPH_JS_PARTS = (
    "graph-state.js",
    "graph-artifacts.js",
    "graph-noop-evidence.js",
    "graph-right-panel.js",
    "graph-cues.js",
    "graph-build.js",
    "graph-selection.js",
    "graph-render.js",
)
GRAPH_JS = "\n".join(
    Path(f"src/ui/static/graph/{name}").read_text(encoding="utf-8")
    for name in _GRAPH_JS_PARTS
)
# Existing static-contract tests search the asset that now owns the code/CSS.
PANEL_HTML = PANEL_HTML_ONLY + "\n" + PANEL_CSS + "\n" + PANEL_JS + "\n" + GRAPH_JS




def test_panel_loads_split_static_assets():
    assert '<link rel="stylesheet" href="/static/panel.css">' in PANEL_HTML_ONLY
    assert '<script src="https://d3js.org/d3.v7.min.js"></script>' in PANEL_HTML_ONLY
    for name in _GRAPH_JS_PARTS:
        assert f'<script src="/static/graph/{name}"></script>' in PANEL_HTML_ONLY
    assert '<script src="/static/panel.js"></script>' in PANEL_HTML_ONLY
    assert '<style>' not in PANEL_HTML_ONLY
    assert '<script>' not in PANEL_HTML_ONLY


def test_panel_static_assets_are_served():
    client = TestClient(app)
    paths = [
        ('/static/panel.css', 'text/css'),
        ('/static/panel.js', 'javascript'),
    ] + [(f'/static/graph/{name}', 'javascript') for name in _GRAPH_JS_PARTS]
    for path, expected in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.headers['content-type']
        assert response.headers['cache-control'] == 'no-store'

    html = client.get('/')
    assert html.status_code == 200
    assert html.headers['cache-control'] == 'no-store'
    assert '/static/panel.css' in html.text
    for name in _GRAPH_JS_PARTS:
        assert f'/static/graph/{name}' in html.text
    assert '/static/panel.js' in html.text


def test_panel_served_html_cache_busts_local_static_assets():
    html = TestClient(app).get('/')

    assert html.status_code == 200
    assets = ['panel.css', 'panel.js'] + [f'graph/{name}' for name in _GRAPH_JS_PARTS]
    for asset in assets:
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
    session_ready_case = PANEL_HTML.split("case 'session_ready':", 1)[1].split(
        "case 'task_started':", 1
    )[0]

    assert "const agentModel  = document.getElementById('agent-model');" in PANEL_HTML
    assert "function setAgentModel(modelName)" in PANEL_HTML
    assert "setAgentModel(ev.model_name);" in PANEL_HTML
    assert "addRow('dim', 'agent ready.');" not in session_ready_case


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


def test_panel_graph_has_view_controls_and_vertical_top_right_legend():
    assert 'id="graph-controls" class="graph-controls"' in PANEL_HTML
    assert 'id="graph-fit" class="icon-only" type="button" aria-label="Show all graph nodes"' in PANEL_HTML
    assert 'id="graph-zoom-in" class="icon-only" type="button" aria-label="Zoom graph in"' in PANEL_HTML
    assert 'id="graph-zoom-out" class="icon-only" type="button" aria-label="Zoom graph out"' in PANEL_HTML
    assert "function fitToNodes()" in PANEL_HTML
    assert "function zoomBy(factor)" in PANEL_HTML
    assert "zoomBehavior.scaleBy" in PANEL_HTML
    assert "zoomBehavior.transform" in PANEL_HTML

    assert '<div class="legend-title">action count</div>' in PANEL_HTML


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
    assert "buildSequentialLinks(urlNode.viewportSequence, viewportIds, null)" in viewport_builder
    assert "viewports.map(vp => ({ source: root.id, target: vp.id" not in viewport_builder
    assert "nodes: viewports," in viewport_builder

    action_builder = PANEL_HTML.split("function buildActionGraphData(viewportId)", 1)[1].split(
        "function trajectoryLabelFor(n)", 1
    )[0]
    assert "buildSequentialLinks(viewportNode.actionSequence, actionIds, null, true)" in action_builder
    assert "actions.map(action => ({ source: root.id, target: action.id" not in action_builder
    assert "nodes: actions," in action_builder


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
    assert "if (actionName === 'navigate') return `Open ${truncateLabel(values.url || 'page', 40)}`;" in PANEL_HTML
    assert "return String(actionName || 'Action').replace(/_/g, ' ');" in PANEL_HTML


def test_panel_graph_truncates_rendered_node_labels_without_changing_data_labels():
    assert "const GRAPH_NODE_LABEL_MAX_CHARS = 28;" in PANEL_HTML
    assert "function compactGraphNodeLabel(label, maxChars = GRAPH_NODE_LABEL_MAX_CHARS)" in PANEL_HTML
    assert "function displayGraphNodeLabel(d)" in PANEL_HTML
    assert "return text.length <= maxChars ? text : text.slice(0, maxChars - 1) + '…';" in PANEL_HTML
    assert "nodeSel.select('text.graph-node-label').text(displayGraphNodeLabel);" in PANEL_HTML

    graph_renderer = PANEL_HTML.split("function update(payload)", 1)[1].split(
        "function reset()", 1
    )[0]
    assert "nodeSel.select('text').text(d => d.label || d.id);" not in graph_renderer
    assert "label: actionLabel(actionName, actionArgs)" in PANEL_HTML
    assert "const title = d.label || d.host || d.actionName || d.id;" in PANEL_HTML


def test_panel_action_graph_reuses_same_action_nodes_and_draws_cycles():
    assert "function stableActionValue(value)" in PANEL_HTML
    assert "function actionSignature(actionName, args)" in PANEL_HTML
    assert "let actionNodeIdByStep = new Map();" in PANEL_HTML
    assert "const actionId = `action|${viewportId}|${actionSignature(actionName, actionArgs)}`;" in PANEL_HTML
    assert "let actionNode = trajectoryActions.get(actionId);" in PANEL_HTML
    assert "if (!actionNode)" in PANEL_HTML
    assert "stepIds: []," in PANEL_HTML
    assert "actionNode.stepIds.push(stepIdKey);" in PANEL_HTML
    assert "actionNodeIdByStep.set(stepIdKey, actionId);" in PANEL_HTML
    assert "actionNode.visits += 1;" in PANEL_HTML
    assert "viewportNode.actionSequence.push(actionId);" in PANEL_HTML
    assert "buildSequentialLinks(viewportNode.actionSequence, actionIds, null, true)" in PANEL_HTML
    assert "linkG.selectAll('path.graph-link')" in PANEL_HTML
    assert "function linkPath(d)" in PANEL_HTML
    assert "return `M ${sx} ${sy - 8} C" in PANEL_HTML
    assert "function detectCycleEdges(links)" in PANEL_HTML
    assert "const isCycleEdge = !!source && !!target && (source === target || (cyclicNodes.has(source) && cyclicNodes.has(target)));" in PANEL_HTML
    assert "detectCycleEdges(buildSequentialLinks(viewportNode.actionSequence, actionIds, null, true))" in PANEL_HTML
    assert ".classed('cycle', d => !!d.isCycleEdge)" in PANEL_HTML
    assert ".graph-link.cycle" in PANEL_HTML
    assert 'id="graph-arrow-cycle"' in PANEL_HTML


def test_panel_graph_action_artifacts_prioritize_replay_and_inline_compare():
    assert "function renderActionReplayCard(label, href)" in PANEL_HTML
    assert "function renderBeforeAfterCompare(beforeHref, afterHref)" in PANEL_HTML
    assert "class=\"artifact-primary\"" in PANEL_HTML
    # P5: side-by-side .artifact-split was replaced with a CSS clip-path slider
    # overlay so reviewers can scrub between before/after in one viewport.
    assert "class=\"artifact-slider\"" in PANEL_HTML
    assert "class=\"artifact-slider-after\"" in PANEL_HTML
    assert "class=\"artifact-slider-range\"" in PANEL_HTML
    assert "class=\"artifact-split\"" not in PANEL_HTML
    assert "class=\"artifact-compare-tabs\"" not in PANEL_HTML
    assert "data-compare-mode=\"before\"" not in PANEL_HTML
    assert "data-compare-mode=\"after\"" not in PANEL_HTML
    assert "data-compare-mode=\"split\"" not in PANEL_HTML
    assert "Technical paths" in PANEL_HTML

def test_panel_graph_selection_can_show_llm_raw_context_and_response():
    assert "let llmInferencesByStep = new Map();" in PANEL_HTML
    assert "case 'llm_inference':" in PANEL_HTML
    assert "storeLlmInference(ev);" in PANEL_HTML
    assert "window.getLlmInferenceForStep = getLlmInferenceForStep;" in PANEL_HTML
    assert 'id="side-llm-raw-section" class="side-section side-scroll-section side-llm-raw-section" hidden' in PANEL_HTML_ONLY
    assert '<summary data-icon="psychology">View LLM raw context / response</summary>' in PANEL_HTML_ONLY
    assert "function renderLlmInferenceBody(inference)" in PANEL_HTML
    # P5: signature gained an optional actionNode for ARIA pre/post diff.
    assert "function renderRightPanelAuxiliarySections(inference, artifacts, actionNode)" in PANEL_HTML
    assert "View LLM raw context / response" in PANEL_HTML
    assert "Raw context" in PANEL_HTML
    assert "Output response" in PANEL_HTML
    assert "llmInference: llmInferenceForStep(ev.step_id)" in PANEL_HTML
    assert "renderRightPanelAuxiliarySections(d.llmInference, d.artifacts)" in PANEL_HTML
    assert "setOptionalSideSection(llmSection, llmBody, renderLlmInferenceBody(inference));" in PANEL_HTML
    assert "details.side-section[hidden]" in PANEL_HTML
    assert "display: none;" in PANEL_HTML.split("details.side-section[hidden] {", 1)[1].split("}", 1)[0]


def test_panel_selection_can_show_dom_and_aria_state_artifacts():
    step_render = PANEL_HTML.split("function renderActionStepAdditionalInfo(stepId)", 1)[1].split(
        "function actionGroupStepIds", 1
    )[0]
    group_render = PANEL_HTML.split("function renderActionGroupAdditionalInfo(actionNode)", 1)[1].split(
        "window.renderActionStepAdditionalInfo", 1
    )[0]
    graph_node_selection = PANEL_HTML.split("function renderGraphNodeSelection(d)", 1)[1].split(
        "function renderSelection(d)", 1
    )[0]

    assert 'id="side-browser-state-section" class="side-section side-scroll-section side-browser-state-section browser-state-details" hidden' in PANEL_HTML_ONLY
    assert '<summary data-icon="account_tree">View DOM/ARIA State</summary>' in PANEL_HTML_ONLY
    # P5: renderBrowserStateBody gained an optional actionNode arg for ARIA diff.
    assert "function renderBrowserStateBody(artifacts, actionNode)" in PANEL_HTML
    assert "function renderBrowserStateMetaLink(label, href, linkText)" in PANEL_HTML
    assert "View DOM/ARIA State" in PANEL_HTML
    assert "DOM snapshot" in PANEL_HTML
    assert "ARIA snapshot" in PANEL_HTML
    assert "artifacts.html_path || artifacts.after_html_path" in PANEL_HTML
    assert "artifacts.a11y_path || artifacts.after_a11y_path" in PANEL_HTML
    assert "function hydrateBrowserStateButtons(root = document)" in PANEL_HTML
    assert "fetch(src, { cache: 'no-store' })" in PANEL_HTML
    # Step/group selectors thread the action node through so ARIA diff can fire.
    assert "renderRightPanelAuxiliarySections(inference, artifacts, actionNode)" in step_render
    assert "renderRightPanelAuxiliarySections(inference, artifacts, actionNode)" in group_render
    assert "renderRightPanelAuxiliarySections(d.llmInference, d.artifacts)" in graph_node_selection
    assert "hydrateBrowserStateButtons(browserStateSection);" in PANEL_HTML
    assert "if (browserStateSection.open) loadBrowserStatePreviews(browserStateSection);" in PANEL_HTML


def test_panel_has_replay_session_controls():
    assert 'id="sessions-btn"' in PANEL_HTML
    assert 'id="sessions-panel"' in PANEL_HTML
    assert 'id="replay-controls"' in PANEL_HTML
    assert 'id="replay-badge"' not in PANEL_HTML
    assert "const replayBadge" not in PANEL_HTML


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
    assert "setStatus('connected', 'replay')" not in PANEL_HTML


def test_panel_links_replay_screenshots_from_action_artifacts():
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]
    assert "storeArtifactsForStep(ev.step_id, ev.artifacts);" in action_case
    step_render = PANEL_HTML.split("function renderActionStepAdditionalInfo(stepId)", 1)[1].split(
        "function renderTimelineActionStepInfo", 1
    )[0]
    assert "renderActionArtifacts(artifacts)" in step_render


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


def test_panel_graph_tracks_global_url_sequence():
    # Global URL nav order is needed for layer-1 cue detection.
    assert "let urlSequence = [];" in PANEL_HTML
    record_nav = PANEL_HTML.split("function recordNavigation(url, stepId)", 1)[1].split(
        "function recordActionExecution", 1
    )[0]
    assert "urlSequence.push(key);" in record_nav
    reset_fn = PANEL_HTML.split("function resetTrajectoryGraphState()", 1)[1].split(
        "function ", 1
    )[0]
    assert "urlSequence.length = 0;" in reset_fn or "urlSequence = [];" in reset_fn


def test_panel_graph_compute_own_cues_emits_four_motif_types():
    # P2 (outline §F2): cue function emits cycle/repeated/noop/deadEnd per layer.
    assert "function computeOwnCues(type, node, cyclicSet, outcome)" in GRAPH_JS
    body = GRAPH_JS.split("function computeOwnCues(type, node, cyclicSet, outcome)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    for key in ("cycle", "repeated", "noop", "deadEnd"):
        assert f"{key}," in body or f"{key}:" in body, f"missing cue key {key}"
    # Cycle membership is set-driven (SCC), not a fragile A→B→A bounce.
    assert "cyclicSet.has(node.id)" in body
    # Repeated is amber (own attention but not red).
    assert "'amber'" in body
    assert "'red'" in body
    # noop is action-only.
    assert "type === 'action'" in body and "noopFlag(node)" in body
    # Dead-end gated on outcome.
    assert "isDeadEndCandidate(type, node, outcome)" in body


def test_panel_graph_cycle_detection_reused_from_scc():
    # P2: detectCycleEdges must delegate to the extracted SCC helper so cue
    # computation and edge highlighting share the same definition of cycle.
    assert "function computeCyclicNodes(links)" in GRAPH_JS
    detect_body = GRAPH_JS.split("function detectCycleEdges(links) {", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "computeCyclicNodes(links)" in detect_body


def test_panel_graph_build_cue_context_precomputes_layer_cyclic_sets():
    body = GRAPH_JS.split("function buildCueContext()", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # Three layer-specific cyclic sets seed cue computation.
    assert "urlCyclic" in body
    assert "viewportCyclicByUrl" in body
    assert "actionCyclicByViewport" in body
    assert "computeCyclicNodes(" in body
    # Outcome is threaded through for dead-end gating (set by P3).
    assert "trajectoryOutcome" in body


def test_panel_graph_rollup_breakdown_covers_all_four_motif_types():
    body = GRAPH_JS.split("function rollupCueFor(type, scope, context)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # breakdown initialized with all four cue types.
    for key in ("cycle:", "repeated:", "noop:", "deadEnd:"):
        assert key in body
    # Outline §S2 examples include repeated action and no-op action in collapsed
    # lower-layer badge summaries, so every motif cue contributes to rollupCount.
    assert "count += 1" in body
    assert "cues.cycle || cues.noop || cues.deadEnd" not in body
    # URL badges summarize hidden viewport and action descendants.
    assert "scope.viewportIds" in body
    assert "scope.actionIds" in body


def test_panel_graph_builders_attach_cue_fields():
    for fn in ("buildUrlGraphData", "buildViewportGraphData", "buildActionGraphData"):
        body = GRAPH_JS.split(f"function {fn}", 1)[1].split(
            "\nfunction ", 1
        )[0]
        assert "buildCueContext()" in body or "cueContext" in body, f"{fn} must use cue context"
        assert "attachCueFields" in body, f"{fn} must attach cue fields"
    # Cue lookup goes through the cached ownCuesById map, not a recomputation.
    attach_body = GRAPH_JS.split("function attachCueFields(", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "context.ownCuesById.get(src.id)" in attach_body
    assert "badgeCount" in attach_body
    # Badge principle: own-layer cues already visible in the current graph layer
    # must not inflate badgeCount. Badges summarize lower layers only.
    assert "badgeCount = rollupCount" in attach_body
    assert "ownRedCount" not in attach_body


def test_panel_graph_dominant_cue_priority_ordering():
    # Outline §S2 badge principle: an own-layer cue with another visual channel
    # must NOT also appear in the badge.
    #   repeated → encoded by node fill+radius
    #   cycle    → encoded by edge highlight
    #   deadEnd  → encoded by cue-ring stroke (terminal outline)
    #   noop     → encoded by cue-ring stroke (no-op outline) plus detail-panel evidence
    # Rollup badges surface every cue type named by outline §S2 examples so
    # collapsed parents advertise descendant cues hidden by collapse.
    rollup_decl = GRAPH_JS.split("const ROLLUP_CUE_PRIORITY =", 1)[1].split(";", 1)[0]
    for included in ("'deadEnd'", "'cycle'", "'noop'", "'repeated'"):
        assert included in rollup_decl, f"{included} should surface collapsed lower-layer cues"
    assert "const CUE_PRIORITY" not in GRAPH_JS
    assert "dominantOwnCueType" not in GRAPH_JS


def test_panel_graph_badges_are_rollup_only():
    # Outline §S2: badges summarize collapsed lower-layer cues only. Action
    # nodes have no lower layer, so own action cues are not rendered as badges.
    badge_body = GRAPH_JS.split("function cueBadgeClass(d)", 1)[1].split("}\n", 1)[0]
    assert "ownType" not in badge_body
    assert "dominantOwnCueType" not in badge_body
    assert "rollupType" in badge_body
    # Badge exposes a glyph and a cue-type class.
    assert "cue-${" in badge_body or "cue-${rollupType}" in badge_body
    assert "CUE_GLYPH" in GRAPH_JS


def test_panel_graph_renders_cue_ring_on_nodes():
    # Cue-ring SVG element is appended on enter and reflects dead-end/no-op cues.
    update_body = GRAPH_JS.split("function update(payload) {", 1)[1].split(
        "\n  function reset()", 1
    )[0]
    assert "'cue-ring'" in update_body
    assert "ownCueRingType(d)" in update_body
    ring_body = GRAPH_JS.split("function ownCueRingType(d)", 1)[1].split("\nfunction ", 1)[0]
    assert "d.ownCues.deadEnd" in ring_body
    assert "d.ownCues.noop" in ring_body
    # Badge label combines glyph + count once count ≥ 2.
    assert "d.badgeCount >= 2" in update_body


def test_panel_css_cue_ring_and_typed_badge_styles():
    for sel in (
        ".graph-node circle.cue-ring",
        ".graph-node circle.cue-ring.cue-deadEnd",
        ".graph-node circle.cue-ring.cue-noop",
        ".cue-legend-swatch.cue-noop",
        ".cue-legend-swatch.cue-currentNode",
        ".cue-legend-swatch.cue-selectedNode",
        ".node-cue-badge circle.cue-cycle",   # rollup badge for cycle still needed
        ".node-cue-badge circle.cue-deadEnd",
        ".node-cue-badge circle.cue-noop",
        ".node-cue-badge circle.cue-repeated",
    ):
        assert sel in PANEL_CSS, f"missing css rule: {sel}"
    # Cues that have another visual channel get no ring/badge.
    for absent in (
        ".graph-node circle.cue-ring.cue-repeated",
        ".graph-node circle.cue-ring.cue-cycle",
    ):
        assert absent not in PANEL_CSS, f"unexpected css rule: {absent}"


def test_noop_alert_renders_above_compare_when_isnoop():
    # Outline §F2.4: no-op outcome cue surfaces as a banner above the
    # before/after compare only after DOM, ARIA, and screenshot evidence all
    # satisfy the <= K no-change threshold.
    body = GRAPH_JS.split("function renderActionArtifacts(artifacts", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # No longer accepts/trusts caller-supplied isNoop or same screenshot path alone.
    assert "function renderActionArtifacts(artifacts)" in GRAPH_JS
    assert "beforeShot === afterShot" not in body
    # Renders the alert class above artifact-compare (cards array order).
    assert "artifact-noop-alert" in body
    assert 'hidden data-noop-evidence="true"' in body
    assert "Checking no-op evidence" in body
    compare_pos = body.find("renderBeforeAfterCompare(beforeShot, afterShot)")
    alert_pos = body.find("noopAlert,")
    assert 0 < alert_pos < compare_pos, "noop alert must precede compare in cards array"
    assert "hydrateNoopEvidence(sideReplay);" in PANEL_JS
    assert "hydrateNoopEvidence(replayEl);" in GRAPH_JS


def test_noop_alert_css_present():
    assert ".artifact-noop-alert" in PANEL_CSS
    assert ".artifact-noop-alert[hidden]" in PANEL_CSS
    assert ".artifact-noop-text" in PANEL_CSS


def test_p5_action_node_carries_raw_pre_post_aria_text():
    # P5: noop signatures alone can't be diffed in the UI; the raw text must
    # also flow onto each action node and into trajectoryLastSnapshot.
    record_body = GRAPH_JS.split("function recordActionExecution(ev)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "postAriaText = (ev.artifacts && ev.artifacts.aria_snapshot) || ''" in record_body
    assert "preAriaText = preSnap ? (preSnap.ariaText || '') : ''" in record_body
    assert "preAriaText," in record_body
    assert "postAriaText," in record_body
    assert "ariaText: postAriaText," in record_body


def test_p5_aria_pre_post_diff_renderer_is_set_based():
    helper = GRAPH_JS.split("function ariaDiffLines(", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # Removals and additions derive from set membership.
    assert "preSet = new Set(preLines)" in helper
    assert "postSet = new Set(postLines)" in helper
    assert "kind: 'removed'" in helper
    assert "kind: 'added'" in helper
    # Truncated flag prevents the panel from rendering pathologically long diffs.
    assert "truncated = true" in helper
    renderer = GRAPH_JS.split("function renderAriaPrePostDiff(", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "ariaDiffLines(preText, postText)" in renderer
    assert "aria-diff-line" in renderer
    assert "ARIA diff" in renderer


def test_p5_browser_state_body_injects_aria_diff_when_action_node_known():
    body = GRAPH_JS.split("function renderBrowserStateBody(artifacts, actionNode)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "renderAriaPrePostDiff(actionNode.preAriaText, actionNode.postAriaText)" in body
    # When no action node is available (e.g. URL/viewport selection) the
    # diff block is skipped but DOM/ARIA artifact links still render.
    assert "actionNode\n" in body or "actionNode ?" in body


def test_p5_before_after_slider_uses_clip_path_split():
    renderer = GRAPH_JS.split("function renderBeforeAfterCompare(beforeHref, afterHref)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "artifact-slider" in renderer
    assert "--split" in renderer
    assert "artifact-slider-before" in renderer
    assert "artifact-slider-after" in renderer
    assert "type=\"range\"" in renderer
    # CSS implements the actual reveal.
    assert ".artifact-slider .artifact-slider-after" in PANEL_CSS
    assert "clip-path: inset(0 0 0 var(--split" in PANEL_CSS


def test_p5_noop_alert_requires_dom_aria_and_screenshot_thresholds():
    renderer = GRAPH_JS.split("function renderBeforeAfterCompare(beforeHref, afterHref)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "artifact-visual-diff" not in renderer
    assert "Visual diff" not in renderer
    helper = GRAPH_JS.split("function hydrateNoopEvidence(root = document)", 1)[1].split(
        "\n// Set-based ARIA diff", 1
    )[0]
    assert "NOOP_EVIDENCE_DIFF_THRESHOLD = 0.01" in GRAPH_JS
    assert "function evaluateNoopEvidence(artifacts)" in GRAPH_JS
    assert "function primeNoopEvidenceForAction(actionNode)" in GRAPH_JS
    assert ".artifact-noop-alert[data-noop-evidence]:not([data-noop-ready])" in helper
    evidence_helper = GRAPH_JS.split("function evaluateNoopEvidence(artifacts)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "fetchArtifactTextByName(paths.beforeHtml)" in evidence_helper
    assert "fetchArtifactTextByName(paths.afterHtml)" in evidence_helper
    assert "fetchArtifactTextByName(paths.beforeAria)" in evidence_helper
    assert "fetchArtifactTextByName(paths.afterAria)" in evidence_helper
    assert "screenshotDiffRatio(" in evidence_helper
    assert "domRatio === 0" in evidence_helper
    assert "ariaRatio === 0" in evidence_helper
    assert "screenshotRatio <= NOOP_EVIDENCE_DIFF_THRESHOLD" in evidence_helper
    screenshot_helper = GRAPH_JS.split("function screenshotDiffRatio(beforeSrc, afterSrc)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "getImageData(0, 0, w, h)" in screenshot_helper
    assert "changedPixels" in screenshot_helper
    assert "window.hydrateNoopEvidence = hydrateNoopEvidence;" in GRAPH_JS
    prime_body = GRAPH_JS.split("function primeNoopEvidenceForAction(actionNode)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "actionNode.noopEvidenceKey = evidenceKey" in prime_body
    assert "actionNode.noopEvidenceStatus = evidence.ok ? 'pass' : 'fail'" in prime_body
    assert "scheduleGraphUpdate();" in prime_body


def test_p5_aria_diff_styles_and_truncation_hint():
    for sel in (
        ".aria-diff",
        ".aria-diff-line.added",
        ".aria-diff-line.removed",
        ".aria-diff-prefix",
        ".aria-diff-truncated",
    ):
        assert sel in PANEL_CSS, f"missing diff style: {sel}"
    assert ".artifact-visual-diff" not in PANEL_CSS


def test_graph_cue_legend_pinned_bottom_right_with_motif_and_highlight_rows():
    # Legend reflects motif cues plus the node-selection stroke accents:
    #   dead end → thick black ring on the node itself
    #   no-op    → thick red ring on the action node itself
    #   current  → bright magenta node stroke
    #   selected → bright blue node stroke after clicking a node/timeline item
    # `cycle` (edge highlight) and `repeated` (node fill/radius) get no legend row.
    assert 'id="graph-cue-legend"' in PANEL_HTML_ONLY
    assert 'aria-label="Graph cue and node highlight legend"' in PANEL_HTML_ONLY
    assert 'data-cue="cycle"' not in PANEL_HTML_ONLY
    assert 'cue-legend-swatch cue-cycle-edge' not in PANEL_HTML_ONLY
    assert '>cycle (edge)<' not in PANEL_HTML_ONLY
    assert 'data-cue="deadEnd"' in PANEL_HTML_ONLY
    assert 'cue-legend-swatch cue-deadEnd' in PANEL_HTML_ONLY
    assert '<span class="cue-legend-glyph" aria-hidden="true">■</span>' not in PANEL_HTML_ONLY
    assert '>dead end<' in PANEL_HTML_ONLY
    assert 'data-cue="noop"' in PANEL_HTML_ONLY
    assert 'cue-legend-swatch cue-noop' in PANEL_HTML_ONLY
    assert '>no-op<' in PANEL_HTML_ONLY
    assert 'data-cue="currentNode"' in PANEL_HTML_ONLY
    assert 'cue-legend-swatch cue-currentNode' in PANEL_HTML_ONLY
    assert '>current node<' in PANEL_HTML_ONLY
    assert 'data-cue="selectedNode"' in PANEL_HTML_ONLY
    assert 'cue-legend-swatch cue-selectedNode' in PANEL_HTML_ONLY
    assert '>selected node<' in PANEL_HTML_ONLY
    for absent in ('data-cue="repeated"', 'data-cue="cycle"'):
        assert absent not in PANEL_HTML_ONLY, f'{absent} should be removed from legend'
    # Pinned to bottom-right.
    css_block = PANEL_CSS.split('.graph-cue-legend {', 1)[1].split('}', 1)[0]
    assert 'bottom: 14px' in css_block
    assert 'right: 14px' in css_block
    # Show/hide piggy-backs on the existing updateGraphLegend trigger so the
    # legend appears only after the first node is rendered.
    legend_update = GRAPH_JS.split('function updateGraphLegend(maxWorkCount, hasNodes)', 1)[1].split(
        '\n  function ', 1
    )[0]
    assert 'cueLegendEl.classList.toggle' in legend_update


def test_p5_panel_threads_action_node_into_auxiliary_sections():
    assert "window.actionNodeForStep = actionNodeForStep;" in GRAPH_JS
    assert "function actionNodeForStep(stepId)" in GRAPH_JS
    # Step-level selector resolves the action node before rendering.
    step_render = PANEL_JS.split("function renderActionStepAdditionalInfo(stepId)", 1)[1].split(
        "function actionGroupStepIds", 1
    )[0]
    assert "window.actionNodeForStep(key)" in step_render


def test_panel_dispatches_setTrajectoryOutcome_on_task_lifecycle_events():
    # P3: panel.js must forward outcome metadata from the WebSocket terminal
    # events into the graph so dead-end / dead-action cues can fire.
    body = PANEL_JS
    for case_key, success in (
        ("case 'task_complete':", "taskSuccess: true"),
        ("case 'task_failed':", "taskSuccess: false"),
        ("case 'task_interrupted':", "taskSuccess: false"),
    ):
        # Each terminal-event handler invokes the global setter with the right success flag.
        chunk = body.split(case_key, 1)[1].split("break;", 1)[0]
        assert "dispatchTrajectoryOutcome" in chunk, f"{case_key} missing outcome dispatch"
        assert success in chunk, f"{case_key} missing {success}"
        assert "terminalStepId: ev.terminal_step_id" in chunk
    assert "window.setTrajectoryOutcome(outcome);" in body
    # Setter is exported on the window from graph.js so panel.js can call it.
    assert "window.setTrajectoryOutcome = setTrajectoryOutcome;" in GRAPH_JS


def test_panel_graph_trajectory_outcome_stub_present():
    # P2 declares the outcome holder; P3 fills it. Reset must clear it.
    assert "let trajectoryOutcome" in GRAPH_JS
    assert "function setTrajectoryOutcome(" in GRAPH_JS
    reset_body = GRAPH_JS.split("function resetTrajectoryGraphState() {", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "trajectoryOutcome = null;" in reset_body


def test_panel_graph_renders_cue_badge_with_severity_matrix():
    update_body = PANEL_HTML.split("function update(payload) {", 1)[1].split(
        "function reset()", 1
    )[0]
    # Badge group is attached on enter
    assert ".node-cue-badge" in update_body
    assert "g').attr('class', 'node-cue-badge'" in update_body or 'class\', \'node-cue-badge\'' in update_body
    # Badge visibility gated on badgeCount > 0
    assert "d.badgeCount > 0" in update_body or "d.badgeCount >= 1" in update_body
    # Badge severity is rollup-only; own-layer cues use primary encodings.
    assert "own-red" not in update_body
    assert "rollup-red" in update_body
    # Rollup badges use one readable text style over their cue-specific badge.
    assert "on-fill" not in update_body
    assert "on-stroke" in update_body


def test_panel_graph_tooltip_includes_cue_breakdown():
    tooltip_block = PANEL_HTML.split("function showTooltip(event, d) {", 1)[1].split(
        "function moveTooltip(event)", 1
    )[0]
    # Section header + per-type rows for all four motif types.
    assert "Cues" in tooltip_block
    for label in ("cycle", "repeated", "no-op", "dead end"):
        assert label in tooltip_block
    # own / inside split preserved.
    assert "own" in tooltip_block
    assert "inside" in tooltip_block
    # Guarded: only renders when something to show
    assert "d.badgeCount" in tooltip_block or "d.ownCues" in tooltip_block


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


def test_panel_plan_items_jump_to_subgoal_start_rows():
    render_plan = PANEL_HTML.split("function renderPlan()", 1)[1].split(
        "function upsertActionSummary", 1
    )[0]
    subgoal_started_case = PANEL_HTML.split("case 'subgoal_started':", 1)[1].split(
        "case 'subgoal_completed':", 1
    )[0]

    assert "let subgoalStartRowsById = new Map();" in PANEL_HTML
    assert "function recordSubgoalStart(subgoalId, row)" in PANEL_HTML
    assert "function jumpToSubgoalStart(subgoalId)" in PANEL_HTML
    assert "function flashSubgoalStartRow(row)" in PANEL_HTML
    assert "subgoalStartRowsById.set(key, row);" in PANEL_HTML
    assert "row.dataset.subgoalId = key;" in PANEL_HTML
    assert "row.scrollIntoView({ block: 'center', behavior: 'smooth' });" in PANEL_HTML
    assert "activateMainView('timeline', { scrollSelection: false });" in PANEL_HTML
    assert 'type="button" class="todo ${sg.status}${jumpable ? \' jumpable\' : \'\'}"' in render_plan
    assert 'data-subgoal-id="${escHtml(key || \'\')}"' in render_plan
    assert "sidePlan.querySelectorAll('[data-subgoal-id]').forEach" in render_plan
    assert "jumpToSubgoalStart(item.getAttribute('data-subgoal-id'))" in render_plan
    assert "recordSubgoalStart(" in subgoal_started_case
    assert "addRow('', `<span style=\"color:var(--orange)\">▸</span> subgoal" in subgoal_started_case
    assert ".row.subgoal-anchor.subgoal-jump-highlight" in PANEL_HTML
    assert "@keyframes subgoal-jump-highlight-fade" in PANEL_HTML
    assert "row.addEventListener('animationend'" in PANEL_HTML
    assert "selectedSubgoalId" not in PANEL_HTML
    assert ".todo.jumpable:hover" in PANEL_HTML


def test_panel_graph_uses_top_down_tree_targets():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function isGraphViewActive()", 1
    )[0]

    assert "function rootPosition(" in graph_renderer
    assert "function arrangeGraphNodes(" in graph_renderer
    assert "const GRAPH_TREE_LAYER_SPACING = 96;" in graph_renderer
    assert "const GRAPH_TREE_SIBLING_SPACING = 118;" in graph_renderer
    assert "function buildTopDownLayoutTargets(nodes)" in graph_renderer
    assert "const acyclicLinks = linksData.filter(e => !e.isCycleEdge);" in graph_renderer
    assert "const layoutTargets = buildTopDownLayoutTargets(nodes);" in graph_renderer
    assert "const target = layoutTargets.get(node.id) || { x: 0, y: 90 };" in graph_renderer
    assert "node._targetX = target.x;" in graph_renderer
    assert "node._targetY = target.y;" in graph_renderer
    assert "d3.forceCollide(34).strength(1)" in graph_renderer
    assert "d3.forceManyBody().strength(-160)" in graph_renderer


def test_panel_graph_linear_acyclic_trajectory_targets_single_vertical_column():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function isGraphViewActive()", 1
    )[0]

    assert "function isLinearAcyclicGraph(nodes, acyclicLinks)" in graph_renderer
    assert "if (isLinearAcyclicGraph(orderedNodes, acyclicLinks))" in graph_renderer
    assert "{ x: 0, y: topY + index * GRAPH_TREE_LAYER_SPACING }" in graph_renderer
    assert "const orderedNodes = [...nodes].sort((a, b) => {" in graph_renderer
    assert "const bySequence = (a._sequenceIndex || 0) - (b._sequenceIndex || 0);" in graph_renderer


def test_panel_graph_arranges_with_current_render_links():
    update_body = PANEL_HTML.split("function update(payload) {", 1)[1].split(
        "function reset()", 1
    )[0]

    assert update_body.index("linksData = incomingLinks.map(e => ({ ...e }));") < update_body.index(
        "arrangeGraphNodes(nodesData, prevById);"
    )


def test_panel_graph_root_pin_stays_available_for_root_nodes():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function isGraphViewActive()", 1
    )[0]

    assert "x: graphMode === 'url' ? (index - (count - 1) / 2) * 140 : 0," in graph_renderer
    assert "y: graphMode === 'url' ? -180 : -220," in graph_renderer
    assert "node.fx = pinned.x;" in graph_renderer
    assert "node.fy = pinned.y;" in graph_renderer
    assert "if (d && Number.isFinite(d._targetY)) return d._targetY;" in graph_renderer
    assert "d3.forceCollide(34).strength(1)" in graph_renderer
    assert "d3.forceManyBody().strength(-160)" in graph_renderer
    assert "if (d.isRoot) {" in graph_renderer


def test_panel_graph_breadcrumb_uses_layer_stack_and_clears_context_on_return():
    breadcrumb_renderer = PANEL_HTML.split("function renderBreadcrumb(payload)", 1)[1].split(
        "function update(payload)", 1
    )[0]
    selector = PANEL_HTML.split("function selectGraphActionForStep(stepId)", 1)[1].split(
        "function updateGraphSelectionClass", 1
    )[0]

    assert "function layerName(level)" in PANEL_HTML
    assert "return 'URL layer';" in PANEL_HTML
    assert "return 'Viewport layer';" in PANEL_HTML
    assert "return 'Action layer';" in PANEL_HTML
    assert '<span class="sep">›</span>' in breadcrumb_renderer
    assert '<span class="current-layer">' in breadcrumb_renderer
    assert '<span class="parent-label">inside' in breadcrumb_renderer
    assert "setGraphDrilldown({ level: 'url', urlId: null, viewportId: null });" in breadcrumb_renderer
    assert "setGraphDrilldown({ level: 'viewport', urlId: crumb.urlId, viewportId: null });" in breadcrumb_renderer
    assert "function setGraphDrilldown(next)" in PANEL_HTML
    assert "clearGraphDrillAnchor();" in PANEL_HTML.split("function setGraphDrilldown(next)", 1)[1].split("// ── d3 graph renderer", 1)[0]
    assert "clearGraphDrillAnchor();" in selector
    assert "breadcrumbEl.innerHTML = '<span>URL layer</span>';" in PANEL_HTML



def test_panel_graph_updates_are_deferred_when_graph_tab_is_hidden():
    action_recorder = PANEL_HTML.split("function recordActionExecution(ev)", 1)[1].split(
        "function buildSequentialLinks", 1
    )[0]
    update_fn = PANEL_HTML.split("function updateGraph({ force = false } = {})", 1)[1].split(
        "function scheduleGraphUpdate()", 1
    )[0]
    activate_view = PANEL_HTML.split("function activateMainView(view, options = {})", 1)[1].split(
        "(function setupTabs()", 1
    )[0]

    assert "let graphRenderDirty = false;" in PANEL_HTML
    assert "scheduleGraphUpdate();" in action_recorder
    assert "function isGraphViewActive()" in PANEL_HTML
    assert "document.body.classList.contains('view-graph')" in PANEL_HTML
    assert "if (!force && !isGraphViewActive())" in update_fn
    assert "graphRenderDirty = true;" in update_fn
    assert "graph.update(selectedGraphData());" in update_fn
    assert "updateGraph({ force: true });" in activate_view


def test_panel_graph_performance_avoids_full_force_on_every_update():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function isGraphViewActive()", 1
    )[0]
    update_body = PANEL_HTML.split("function update(payload)", 1)[1].split(
        "function reset()", 1
    )[0]
    node_circle_css = PANEL_HTML.split(".graph-node circle {", 1)[1].split("}", 1)[0]

    assert "contextFrameTick" not in graph_renderer
    assert "updateContextFrameBounds" not in graph_renderer
    assert "const structureChanged =" in update_body
    assert "simulation.alpha(1);" in update_body
    assert "for (let i = 0; i < 300; i++) simulation.tick();" in update_body
    assert "simulation.alpha(0);" in update_body
    assert "simulation.alpha(Math.max(simulation.alpha(), 0.06)).restart();" in update_body
    assert "simulation.alpha(0.6).restart();" not in PANEL_HTML
    assert "filter: drop-shadow" not in node_circle_css

def test_panel_graph_clears_stale_root_flag_when_reusing_nodes():
    graph_renderer = PANEL_HTML.split("const graph = (() => {", 1)[1].split(
        "function isGraphViewActive()", 1
    )[0]

    assert "function normalizeGraphNode(src)" in graph_renderer
    assert "isRoot: false," in graph_renderer
    assert "return Object.assign(prev || {}, normalizeGraphNode(src));" in graph_renderer
    assert "return Object.assign(prev || {}, src);" not in graph_renderer


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
    assert "scrollbar-gutter: stable both-edges;" in sheet_body_css
    assert "overflow: visible;" in side_section_css
    assert "display: grid;" in PANEL_HTML.split("details.side-section[open] {", 1)[1].split("}", 1)[0]
    assert "grid-template-rows: auto minmax(0, auto);" in PANEL_HTML
    assert "max-height: none;" in task_section_css


def test_panel_sidebar_long_content_uses_flow_safe_grid_items():
    side_section_css = PANEL_HTML.split("details.side-section {", 1)[1].split("}", 1)[0]
    side_body_css = PANEL_HTML.split(".side-body {", 1)[1].split("}", 1)[0]
    side_plan_css = PANEL_HTML.split("#side-plan {", 1)[1].split("}", 1)[0]
    todo_css = PANEL_HTML.split(".todo {", 1)[1].split("}", 1)[0]
    action_summary_css = PANEL_HTML.split(".action-summary-card .summary-head {", 1)[1].split("}", 1)[0]

    assert "position: relative;" in side_section_css
    assert "flex: 0 0 auto;" in side_section_css
    assert "width: 100%;" in side_section_css
    assert "min-width: 0;" in side_body_css
    assert "max-width: 100%;" in side_body_css
    assert "word-break: break-word;" in side_body_css
    assert "display: grid;" in side_plan_css
    assert "grid-auto-rows: minmax(28px, auto);" in side_plan_css
    assert "row-gap: 6px;" in side_plan_css
    assert "grid-template-columns: 30px minmax(0, 1fr);" in todo_css
    assert "box-sizing: border-box;" in todo_css
    assert "height: auto;" in todo_css
    assert "min-height: 28px;" in todo_css
    assert "margin: 0;" in todo_css
    assert "white-space: normal;" in todo_css
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


def test_panel_task_complete_renders_browser_agent_speech_bubble():
    review_case = PANEL_HTML.split("case 'review_metadata_extracted':", 1)[1].split(
        "case 'action_executed':", 1
    )[0]
    step_complete_case = PANEL_HTML.split("case 'step_complete':", 1)[1].split(
        "case 'task_complete':", 1
    )[0]
    task_complete_case = PANEL_HTML.split("case 'task_complete':", 1)[1].split(
        "case 'task_failed':", 1
    )[0]
    agent_message_css = PANEL_HTML.split(".row.agent-message {", 1)[1].split("}", 1)[0]

    assert "if (ev.final_result_summary) pendingAgentFinalMessage = ev.final_result_summary;" in review_case
    assert "if (!pendingAgentFinalMessage && ev.final_reasoning) pendingAgentFinalMessage = ev.final_reasoning;" in step_complete_case
    assert "const finalMessage = pendingAgentFinalMessage || ev.final_reasoning || ev.summary;" in task_complete_case
    assert "if (finalMessage) addRow('agent-message', escHtml(finalMessage));" in task_complete_case
    assert "pendingAgentFinalMessage = null;" in task_complete_case
    assert "addBlock('green'," not in task_complete_case
    assert "task complete" not in task_complete_case
    assert "align-self: flex-start;" in agent_message_css
    assert "text-align: left;" in agent_message_css
    assert "background: var(--md-sys-color-secondary-container);" in agent_message_css
    assert "color: var(--md-sys-color-on-secondary-container);" in agent_message_css
    assert "surface-container" not in agent_message_css


def test_panel_task_failed_renders_browser_agent_error_speech_bubble():
    task_failed_case = PANEL_HTML.split("case 'task_failed':", 1)[1].split(
        "case 'task_interrupted':", 1
    )[0]
    failed_message_css = PANEL_HTML.split(".row.agent-message.failed-message {", 1)[1].split("}", 1)[0]
    message_meta_css = PANEL_HTML.split(".row.agent-message .message-meta {", 1)[1].split("}", 1)[0]

    assert "const errorMessage = ev.error_message || 'unknown error';" in task_failed_case
    assert "addRow('agent-message failed-message'," in task_failed_case
    assert '<div class="message-title">task failed</div>' in task_failed_case
    assert '<div class="message-meta">${escHtml(errorMessage)}</div>' in task_failed_case
    assert "addBlock('red'," not in task_failed_case
    assert "background: var(--md-sys-color-error-container);" in failed_message_css
    assert "color: var(--md-sys-color-on-error-container);" in failed_message_css
    assert "color: inherit;" in message_meta_css


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
    assert "function renderActionStepAdditionalInfo(stepId)" in PANEL_HTML
    assert "function renderTimelineActionStepInfo(stepId)" in PANEL_HTML
    assert "return renderActionStepAdditionalInfo(stepId);" in PANEL_HTML
    for label in (
        "Action step number",
        "Summary",
        "Outcome",
        "Reasoning",
        "Function call",
        "Function call arguments",
    ):
        assert label in PANEL_HTML
    assert "Reasoning" in PANEL_HTML
    step_render = PANEL_HTML.split("function renderActionStepAdditionalInfo(stepId)", 1)[1].split(
        "function renderTimelineActionStepInfo", 1
    )[0]
    assert "renderActionArtifacts(artifacts)" in step_render
    assert "renderRightPanelAuxiliarySections(inference, artifacts, actionNode)" in step_render
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
    assert "Function call" in PANEL_HTML
    assert "Function call arguments" in PANEL_HTML


def test_panel_user_chat_message_bubble_keeps_right_edge_but_text_is_left_aligned():
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
    user_message_css = PANEL_HTML.split(".row.user-message {", 1)[1].split("}", 1)[0]
    assert "align-self: flex-end;" in user_message_css
    assert "text-align: left;" in user_message_css
    assert "text-align: right;" not in user_message_css
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
    assert "function renderActionArtifacts(artifacts" in PANEL_HTML
    assert "function replayArtifactHref(path, expectedDir = 'history')" in PANEL_HTML
    assert "beforeScreenshotPath: ev.artifacts && ev.artifacts.before_screenshot_path" in PANEL_HTML
    assert "afterScreenshotPath: ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path)" in PANEL_HTML
    assert "actionGifPath: ev.artifacts && (ev.artifacts.action_clip_gif_path || ev.artifacts.action_gif_path)" in PANEL_HTML
    assert "videoPath: ev.artifacts && ev.artifacts.video_path" in PANEL_HTML
    assert "renderActionReplayCard('Action replay', actionClip)" in PANEL_HTML
    assert "renderBeforeAfterCompare(beforeShot, afterShot)" in PANEL_HTML
    assert "renderArtifactCard('session video', video, 'video')" in PANEL_HTML
    assert "renderActionArtifacts(d.artifacts)" in PANEL_HTML


def test_panel_graph_action_nodes_use_group_additional_info():
    graph_selection = PANEL_HTML.split("function renderSelection(d)", 1)[1].split(
        "function setGraphDrilldown", 1
    )[0]
    graph_node_selection = PANEL_HTML.split("function renderGraphNodeSelection(d)", 1)[1].split(
        "function renderSelection", 1
    )[0]

    assert "function renderGraphNodeSelection(d)" in PANEL_HTML
    assert "if (d.type === 'action')" in graph_selection
    assert "renderActionGroupAdditionalInfo(d);" in graph_selection
    assert "renderActionStepAdditionalInfo(" not in graph_selection
    assert "renderGraphNodeSelection(d);" in graph_selection
    assert "renderActionArtifacts(d.artifacts)" in graph_node_selection
    assert "renderActionPreviewGallery(d.actionPreviews)" in graph_node_selection


def test_panel_graph_and_timeline_selection_share_action_step_highlight_and_info():
    assert ".action-step-group.timeline-highlight" in PANEL_HTML
    assert "function beginActionStepGroup(stepId)" in PANEL_HTML
    assert "currentTimelineStepGroup.dataset.stepId = String(stepId);" in PANEL_HTML
    assert "currentTimelineStepGroup.addEventListener('click'" in PANEL_HTML
    assert "function selectTimelineActionStep(stepId)" in PANEL_HTML
    assert "selectGraphActionForStep(key);" in PANEL_HTML
    assert "renderActionStepAdditionalInfo(selectedTimelineStepId);" in PANEL_HTML
    assert "function highlightTimelineActionStep(stepId)" in PANEL_HTML
    assert "function timelineStepForGraphNode(d)" in PANEL_HTML
    assert "highlightTimelineActionStep(timelineStepForGraphNode(selectedNodeData));" in PANEL_HTML
    assert "highlightTimelineActionStep(null);" in PANEL_HTML
    assert "appendTimelineElement(el);" in PANEL_HTML
    assert "if (currentTimelineStepGroup) currentTimelineStepGroup.appendChild(el);" in PANEL_HTML


def test_panel_select_graph_action_for_step_drills_to_action_layer_and_selects_node():
    selector = PANEL_HTML.split("function selectGraphActionForStep(stepId)", 1)[1].split(
        "function updateGraphSelectionClass", 1
    )[0]

    assert "const actionId = actionNodeIdByStep.get(key);" in selector
    assert "const actionNode = actionId ? trajectoryActions.get(actionId) : null;" in selector
    assert "graphDrilldown = { level: 'action', urlId: actionNode.urlId, viewportId: actionNode.viewportId };" in selector
    assert "selectedNodeId = actionNode.id;" in selector
    assert "selectedNodeData = actionNode;" in selector
    assert "updateGraph();" in selector


def test_panel_action_group_info_lists_members_and_links_to_single_step_detail():
    assert "function renderActionGroupAdditionalInfo(actionNode)" in PANEL_HTML
    group_render = PANEL_HTML.split("function renderActionGroupAdditionalInfo(actionNode)", 1)[1].split(
        "window.renderActionGroupAdditionalInfo", 1
    )[0]

    for label in (
        "Action steps",
        "Summary",
        "Outcome",
        "Reasoning",
        "Function call",
        "Function call arguments",
    ):
        assert label in group_render
    assert "related action steps" in group_render
    assert "data-action-member-step" in group_render
    assert "selectTimelineActionStep(stepId);" in group_render


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
    assert "return { update, reset, resize, refreshSelection, refreshRunning, fitToNodes };" in PANEL_HTML
    assert "updateGraphRunningClass();" in PANEL_HTML


def test_panel_graph_uses_total_action_steps_for_work_color_scale():
    assert "fill: var(--graph-node-fill, var(--surface-2));" in PANEL_HTML
    assert "function actionStepCountForActionIds(actionIds)" in PANEL_HTML
    assert "actionStepCount: actionStepCountForActionIds(src.actionIds)" in PANEL_HTML
    assert "actionStepCount: actionStepCountForActionIds(vp.actionIds)" in PANEL_HTML
    assert "actionStepCount: actionStepCountForAction(action)" in PANEL_HTML
    assert "function graphNodeWorkCount(d)" in PANEL_HTML
    work_count = PANEL_HTML.split("function graphNodeWorkCount(d)", 1)[1].split(
        "function graphNodeFill", 1
    )[0]
    assert "if (Number.isFinite(d.actionStepCount)) return d.actionStepCount;" in work_count
    assert "if (Array.isArray(d.stepIds) && d.stepIds.length) return d.stepIds.length;" in work_count
    assert "if (Number.isFinite(d.actionCount)) return d.actionCount;" in work_count
    assert work_count.index("d.actionStepCount") < work_count.index("d.actionCount")
    assert "function graphNodeFill(d, maxWorkCount)" in PANEL_HTML
    assert "d3.interpolateViridis(0.12)" in PANEL_HTML
    assert "Math.sqrt(Math.min(count, maxWorkCount) / maxWorkCount)" in PANEL_HTML
    assert "d3.interpolateViridis(t)" in PANEL_HTML
    assert "d3.interpolateBlues" not in PANEL_HTML
    assert "const maxWorkCount = Math.max(1, trajectoryMaxWorkCount(), ...nodesData.map(graphNodeWorkCount));" in PANEL_HTML
    assert "function trajectoryMaxWorkCount()" in PANEL_HTML
    assert ".style('--graph-node-fill', d => graphNodeFill(d, maxWorkCount));" in PANEL_HTML
    assert "stroke: transparent;" in PANEL_HTML
    assert "stroke-width: 0;" in PANEL_HTML
    assert ".graph-node.viewport circle { stroke:" not in PANEL_HTML
    assert ".graph-node.action circle { stroke:" not in PANEL_HTML
    assert "rgba(253, 214, 99, 0.12)" not in PANEL_HTML
    assert "rgba(129, 201, 149, 0.12)" not in PANEL_HTML


def test_panel_current_node_accent_preserves_work_fill():
    current_rule = PANEL_HTML.split(".graph-node.current circle {", 1)[1].split("}", 1)[0]
    assert "stroke: var(--graph-accent-current);" in current_rule
    assert "stroke-width: 3;" in current_rule
    assert "fill:" not in current_rule
    assert "filter:" not in current_rule


def test_panel_graph_base_nodes_hide_stroke_until_accented():
    base_rule = PANEL_HTML.split(".graph-node circle {", 1)[1].split("}", 1)[0]
    assert "stroke: transparent;" in base_rule
    assert "stroke-width: 0;" in base_rule
    assert "stroke-width 0.16s ease" in base_rule
    assert ".graph-node.root circle" in PANEL_HTML
    assert ".graph-node.url circle" in PANEL_HTML
    assert ".graph-node.viewport circle" in PANEL_HTML
    assert ".graph-node.action circle" in PANEL_HTML
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
    assert '<div class="legend-title">action count</div>' in PANEL_HTML
    assert "data-legend-max" in PANEL_HTML
    assert "<span>few steps</span>" not in PANEL_HTML
    assert "<span>0</span>" in PANEL_HTML
    assert "<span data-legend-max>1</span>" in PANEL_HTML
    legend_css = PANEL_HTML.split(".graph-legend {", 1)[1].split(".graph-legend.hidden", 1)[0]
    assert "top: 64px;" in legend_css
    assert "right: 14px;" in legend_css
    assert "bottom: 14px;" not in legend_css
    assert "background: linear-gradient(0deg, #482878 0%, #3e4989 25%, #26828e 50%, #35b779 75%, #fde725 100%);" in PANEL_HTML
    assert "flex-direction: row;" in PANEL_HTML
    assert "flex-direction: column-reverse;" in PANEL_HTML
    assert "const legendEl = document.getElementById('graph-legend');" in PANEL_HTML
    assert "function updateGraphLegend(maxWorkCount, hasNodes)" in PANEL_HTML
    assert "const roundedMaxWorkCount = Math.round(Number(maxWorkCount) || 0);" in PANEL_HTML
    assert "maxLabel.textContent = `${roundedMaxWorkCount}`;" in PANEL_HTML
    assert "updateGraphLegend(maxWorkCount, nodesData.length > 0);" in PANEL_HTML
    assert "updateGraphLegend(1, false);" in PANEL_HTML


def test_panel_graph_hover_tooltip_stays_compact():
    tooltip_block = PANEL_HTML.split("function showTooltip(event, d) {", 1)[1].split("function moveTooltip(event)", 1)[0]
    assert "const title = d.label || d.host || d.actionName || d.id;" in tooltip_block
    assert "<span>level</span>" in tooltip_block
    assert "<span>total steps</span>" in tooltip_block
    assert "<span>unique actions</span>" in tooltip_block
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
    artifact_renderer = PANEL_HTML.split("function renderActionArtifacts(artifacts", 1)[1].split(
        "function actionPreviewArtifactsFor(action)", 1
    )[0]
    assert "const actionClip = replayArtifactHref(artifacts.action_clip_gif_path, 'history');" in artifact_renderer
    assert "const fallbackActionGif = replayArtifactHref(artifacts.action_gif_path, 'history');" in artifact_renderer
    assert "renderActionReplayCard('Action replay', actionClip)" in artifact_renderer
    assert "!actionClip && fallbackActionGif ? renderArtifactCard('Before/after GIF', fallbackActionGif) : ''" in artifact_renderer
    assert "action_clip_gif_path" in PANEL_HTML

def test_panel_submit_task_handles_ok_false_and_preserves_input():
    submit_task = PANEL_HTML.split("async function submitTask() {", 1)[1].split("async function interruptTask()", 1)[0]
    assert "const data = await res.json();" in submit_task
    assert "if (!data.ok) throw new Error(data.error || 'Task rejected');" in submit_task
    assert "input.value = '';" not in submit_task.split("try {")[0]
    assert "input.value = '';" in submit_task.split("try {")[1]

def test_panel_interrupt_task_handles_ok_false():
    interrupt_task = PANEL_HTML.split("async function interruptTask() {", 1)[1].split("btn.addEventListener('click'", 1)[0]
    assert "const data = await res.json();" in interrupt_task
    assert "if (!data.ok) throw new Error(data.error || 'Interrupt rejected');" in interrupt_task

def test_panel_stop_button_not_shown_during_is_submitting():
    update_controls = PANEL_HTML.split("function updateControlStates() {", 1)[1].split("}", 1)[0]
    assert "const stopMode = isRunning && !replayMode;" in update_controls
    assert "stopMode = (isRunning || isSubmitting)" not in update_controls

def test_panel_replay_mode_processes_live_events_for_state_but_not_ui():
    ws_onmessage = PANEL_HTML.split("ws.onmessage = (e) => {", 1)[1].split("};", 1)[0]
    assert "if (ev.type === 'task_started') liveIsRunning = true;" in ws_onmessage
    assert "if (ev.type === 'task_complete' || ev.type === 'task_failed' || ev.type === 'task_interrupted') liveIsRunning = false;" in ws_onmessage
    assert "if (replayMode) return;" in ws_onmessage
    
    live_btn = PANEL_HTML.split("liveBtn.addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "isRunning = liveIsRunning;" in live_btn


def test_graph_exposes_aria_diff_signature_and_noop_tracking():
    # P1: no-op detection infrastructure (outline §F2 No-op Action Candidate).
    # The action layer must (a) normalize ARIA snapshots, (b) remember the
    # previous post-state, and (c) expose a noopFlag helper that downstream
    # cue computation in P2 can consume.
    assert "function ariaDiffSignature(text)" in GRAPH_JS
    assert "function noopFlag(actionNode)" in GRAPH_JS
    assert "let trajectoryLastSnapshot" in GRAPH_JS
    # Reset wiring so live → replay → live transitions do not leak state.
    reset_body = GRAPH_JS.split("function resetTrajectoryGraphState() {", 1)[1].split("\nfunction ", 1)[0]
    assert "trajectoryLastSnapshot = null;" in reset_body
    # No-op graph cue is evidence-gated; URL/viewport/ARIA snapshot tracking
    # remains as context, but badges wait for DOM+ARIA+screenshot <= K.
    record_body = GRAPH_JS.split("function recordActionExecution(ev)", 1)[1].split("\nfunction ", 1)[0]
    # P5 wraps the snapshot in postAriaText for both the signature and the raw text.
    assert "(ev.artifacts && ev.artifacts.aria_snapshot)" in record_body
    assert "ariaDiffSignature(postAriaText)" in record_body
    assert "noopEvidenceStatus: 'unknown'" in record_body
    assert "primeNoopEvidenceForAction(actionNode)" in record_body
    noop_body = GRAPH_JS.split("function noopFlag(actionNode)", 1)[1].split("\nfunction ", 1)[0]
    assert "noopEvidenceStatus === 'pass'" in noop_body
    assert "trajectoryLastSnapshot = {" in record_body
