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


def test_panel_graph_mode_toggle_supports_browser_state_graph():
    assert 'data-graph-mode="trajectory"' in PANEL_HTML
    assert 'data-graph-mode="state"' in PANEL_HTML
    assert "function buildStateGraphData()" in PANEL_HTML
    assert "function setupGraphModeToggle()" in PANEL_HTML


def test_panel_reads_state_graph_from_action_artifacts():
    action_case = PANEL_HTML.split("case 'action_executed':", 1)[1].split(
        "case 'step_error':", 1
    )[0]
    assert "recordBrowserStateGraph(ev.artifacts);" in action_case
    assert "no BrowserState graph metadata yet." in PANEL_HTML
    assert ".classed('changed', d => Boolean(d.changed))" in PANEL_HTML


def test_panel_styles_browser_state_graph_node_types():
    assert ".graph-node.group circle" in PANEL_HTML
    assert ".graph-node.leaf circle" in PANEL_HTML
    assert ".graph-node.changed circle" in PANEL_HTML
    assert ".graph-node.changed text" in PANEL_HTML


def test_panel_preserves_drag_in_browser_state_tree_mode():
    assert "function treeDrag()" in PANEL_HTML
    assert ".call(treeDrag())" in PANEL_HTML
    assert "function positionTreeLinks()" in PANEL_HTML
