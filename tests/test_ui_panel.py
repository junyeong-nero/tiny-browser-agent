from pathlib import Path


PANEL_HTML = Path("src/ui/panel.html").read_text(encoding="utf-8")


def test_panel_model_placeholder_is_not_hardcoded_to_gemini():
    assert '<span id="agent-model">gemini</span>' not in PANEL_HTML
    assert '<span id="agent-model">—</span>' in PANEL_HTML


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


def test_panel_disables_live_input_and_ignores_ws_during_replay():
    assert "if (replayMode) return;" in PANEL_HTML
    assert "function setReplayUi(active)" in PANEL_HTML
    assert "setInputEnabled(!active && !isRunning" in PANEL_HTML
    assert "setStatus('connected', 'replay')" in PANEL_HTML


def test_panel_links_replay_screenshots_from_action_artifacts():
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]
    assert "replayArtifactHref(ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path, 'history')" in action_case
    assert "[shot]" in action_case


def test_panel_uses_material_design_theme_tokens():
    assert "family=Roboto" in PANEL_HTML
    # Material Design 3 system color tokens
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


def test_panel_primary_run_button_uses_material_icon_button_style():
    assert "#btn {" in PANEL_HTML
    # M3 Filled Button uses sys color tokens directly
    assert "background: var(--md-sys-color-primary);" in PANEL_HTML
    assert "color: var(--md-sys-color-on-primary);" in PANEL_HTML
    assert 'aria-label="Run task"' in PANEL_HTML
    assert 'title="Run task"' in PANEL_HTML
    assert '<button id="btn" class="icon-only" type="button" aria-label="Run task" title="Run task" disabled>' in PANEL_HTML
    assert "<svg class=\"btn-icon\" aria-hidden=\"true\" viewBox=\"0 0 24 24\" focusable=\"false\">" in PANEL_HTML
    assert "<path d=\"M8 5v14l11-7z\"></path>" in PANEL_HTML
    assert "width: 40px;" in PANEL_HTML
    assert "min-width: 40px;" in PANEL_HTML
    assert "padding: 0;" in PANEL_HTML
    assert "<button id=\"btn\" type=\"button\" disabled>run</button>" not in PANEL_HTML


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


def test_panel_sidebar_task_plan_and_activity_use_scroll_panel_sections():
    assert 'class="side-section side-scroll-section side-task-section"' in PANEL_HTML
    assert 'class="side-section side-scroll-section side-plan-section"' in PANEL_HTML
    assert 'class="side-section side-scroll-section side-activity-section"' in PANEL_HTML
    assert "details.side-scroll-section[open]" in PANEL_HTML
    assert "details.side-scroll-section > .side-body" not in PANEL_HTML


def test_panel_main_card_aligns_to_chat_input_width():
    main_css = PANEL_HTML.split("main#main {", 2)[2].split("}", 1)[0]
    footer_css = PANEL_HTML.split("\n  footer {", 1)[1].split("}", 1)[0]

    assert "margin: 16px 16px 12px;" in main_css
    assert "padding: 4px 16px 16px;" in footer_css


def test_panel_sidebar_itself_is_viewport_constrained_and_scrollable():
    sidebar_css = PANEL_HTML.split("aside#sidebar {", 1)[1].split("}", 1)[0]
    sheet_body_css = PANEL_HTML.split(".sheet-body {", 1)[1].split("}", 1)[0]
    side_section_css = PANEL_HTML.split("details.side-section {", 1)[1].split("}", 1)[0]
    side_scroll_css = PANEL_HTML.split("details.side-scroll-section[open] {", 1)[1].split("}", 1)[0]
    task_section_css = PANEL_HTML.split("details.side-task-section[open] {", 1)[1].split("}", 1)[0]

    # Sheet container fills viewport; rows lay out header / divider / scrollable body / footer.
    assert "display: grid;" in sidebar_css
    assert "grid-template-rows: auto 1px 1fr auto;" in sidebar_css
    assert "height: 100dvh;" in sidebar_css
    assert "max-height: 100dvh;" in sidebar_css
    assert "align-self: stretch;" in sidebar_css
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
    act_item_css = PANEL_HTML.split(".act-item {", 1)[1].split("}", 1)[0]

    assert "position: relative;" in side_section_css
    assert "flex: 0 0 auto;" in side_section_css
    assert "width: 100%;" in side_section_css
    assert "min-width: 0;" in side_body_css
    assert "max-width: 100%;" in side_body_css
    assert "word-break: break-word;" in side_body_css
    assert "grid-template-columns: 30px minmax(0, 1fr);" in todo_css
    assert "grid-template-columns: auto minmax(0, 1fr);" in act_item_css
    assert "align-items: start;" in act_item_css
    assert ".todo .text  { color: var(--fg); min-width: 0; overflow-wrap: anywhere; }" in PANEL_HTML
    assert ".act-item > span:last-child { min-width: 0; overflow-wrap: anywhere; }" in PANEL_HTML


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
    assert '<summary data-icon="history">Activity</summary>' in PANEL_HTML


def test_panel_empty_state_uses_material_symbol_illustration():
    empty_icon_css = PANEL_HTML.split("#empty-state::before {", 1)[1].split("}", 1)[0]

    assert 'content: "travel_explore";' in empty_icon_css
    assert 'font-family: "Material Symbols Rounded";' in empty_icon_css
    assert "border-radius: var(--md-sys-shape-corner-xl);" in empty_icon_css


def test_panel_step_summary_uses_plain_block_without_accent():
    step_complete_case = PANEL_HTML.split("case 'step_complete':", 1)[1].split(
        "case 'task_complete':", 1
    )[0]
    activity_css = PANEL_HTML.split(".act-item {", 1)[1].split("}", 1)[0]
    activity_hover_css = PANEL_HTML.split(".act-item:hover {", 1)[1].split("}", 1)[0]

    assert "addBlock('plain'," in step_complete_case
    assert "addBlock('green'," not in step_complete_case
    assert ".block.plain::before { display: none; }" in PANEL_HTML
    assert ".block.plain {" in PANEL_HTML
    assert "border-left" not in activity_css
    assert "--phase-border" not in activity_css
    assert "--phase-bg" not in activity_css
    assert "--phase-bg" not in activity_hover_css


def test_panel_removes_keybind_help_bar():
    assert 'class="keybind"' not in PANEL_HTML
    assert "enter</kbd> submit" not in PANEL_HTML
    assert "shift+enter</kbd> newline" not in PANEL_HTML
    assert "esc</kbd> interrupt" not in PANEL_HTML
    assert '"keybind resizer aside"' not in PANEL_HTML
    assert 'grid-template-areas: "header" "main" "footer";' in PANEL_HTML


def test_panel_graph_selection_renders_action_before_after_artifacts():
    assert "function renderActionArtifacts(artifacts)" in PANEL_HTML
    assert "function replayArtifactHref(path, expectedDir = 'history')" in PANEL_HTML
    assert "beforeScreenshotPath: ev.artifacts && ev.artifacts.before_screenshot_path" in PANEL_HTML
    assert "afterScreenshotPath: ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path)" in PANEL_HTML
    assert "actionGifPath: ev.artifacts && (ev.artifacts.action_clip_gif_path || ev.artifacts.action_gif_path)" in PANEL_HTML
    assert "videoPath: ev.artifacts && ev.artifacts.video_path" in PANEL_HTML
    assert "renderArtifactCard('action GIF', actionGif)" in PANEL_HTML
    assert "renderArtifactCard('before', beforeShot)" in PANEL_HTML
    assert "renderArtifactCard('after', afterShot)" in PANEL_HTML
    assert "renderArtifactCard('session video', video, 'video')" in PANEL_HTML
    assert "renderActionArtifacts(d.artifacts)" in PANEL_HTML


def test_panel_graph_selection_highlights_timeline_action_step_group():
    assert ".action-step-group.timeline-highlight" in PANEL_HTML
    assert "function beginActionStepGroup(stepId)" in PANEL_HTML
    assert "currentTimelineStepGroup.dataset.stepId = String(stepId);" in PANEL_HTML
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
