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
    assert "function buildSequentialLinks(sequence, allowedIds, rootId = null)" in PANEL_HTML
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
    assert "buildSequentialLinks(viewportNode.actionSequence, actionIds, root.id)" in action_builder
    assert "actions.map(action => ({ source: root.id, target: action.id" not in action_builder


def test_panel_sequence_links_anchor_first_node_and_preserve_returns():
    link_builder = PANEL_HTML.split("function buildSequentialLinks(sequence, allowedIds, rootId = null)", 1)[1].split(
        "function buildTrajectoryGraphData()", 1
    )[0]
    assert "let previous = rootId;" in link_builder
    assert "if (previous && previous !== id)" in link_builder
    assert "const edgeKey = `${previous}|${id}`;" in link_builder
    assert "if (edge) edge.count += 1;" in link_builder


def test_panel_uses_user_friendly_viewport_and_action_labels():
    assert "function scrollLabel(scroll)" in PANEL_HTML
    assert "function viewportLabel(viewport, stepId)" in PANEL_HTML
    assert "function actionLabel(actionName, args)" in PANEL_HTML
    assert "const stepLabel = stepId != null ? `Screen #${stepId}` : 'Screen view';" in PANEL_HTML
    assert "return `${stepLabel} · ${scrollLabel(viewport.scroll)}`;" in PANEL_HTML
    assert "label: viewportLabel(viewport, ev.step_id)" in PANEL_HTML
    assert "label: `#${ev.step_id} ${actionLabel(actionName, actionArgs)}`" in PANEL_HTML
    assert "if (actionName === 'click_at') return `Click at (${values.x}, ${values.y})`;" in PANEL_HTML
    assert "if (actionName === 'navigate') return `Open ${values.url || 'page'}`;" in PANEL_HTML
    assert "return String(actionName || 'Action').replace(/_/g, ' ');" in PANEL_HTML

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
    assert "/sessions/${encodeURIComponent(replaySessionId)}/artifacts/history/" in action_case
    assert "[shot]" in action_case
