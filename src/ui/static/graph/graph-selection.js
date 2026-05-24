let selectedNodeId = null;
let selectedNodeData = null;

function selectGraphNode(d) {
  if (!d) return;
  if (selectedNodeId === d.id) {
    selectedNodeId = null;
    selectedNodeData = null;
  } else {
    selectedNodeId = d.id;
    selectedNodeData = d;
  }
  renderSelection(selectedNodeData);
  highlightTimelineActionStep(timelineStepForGraphNode(selectedNodeData));
  updateGraphSelectionClass();
}

function selectGraphActionForStep(stepId) {
  const key = stepId != null ? String(stepId) : null;
  if (key == null) {
    clearGraphSelection();
    return false;
  }
  const actionId = actionNodeIdByStep.get(key);
  const actionNode = actionId ? trajectoryActions.get(actionId) : null;
  if (!actionNode) {
    clearGraphSelection();
    return false;
  }
  clearGraphDrillAnchor();
  graphDrilldown = { level: 'action', urlId: actionNode.urlId, viewportId: actionNode.viewportId };
  selectedNodeId = actionNode.id;
  selectedNodeData = actionNode;
  updateGraph();
  return true;
}

function clearGraphSelection() {
  if (selectedNodeId === null) return;
  selectedNodeId = null;
  selectedNodeData = null;
  renderSelection(null);
  highlightTimelineActionStep(null);
  updateGraphSelectionClass();
}

function timelineStepForGraphNode(d) {
  if (!d) return null;
  if (d.step != null) return d.step;
  if (d.lastStep != null) return d.lastStep;
  return d.firstStep != null ? d.firstStep : null;
}

function updateGraphSelectionClass() {
  if (typeof graph !== 'undefined' && graph && graph.refreshSelection) {
    graph.refreshSelection();
  }
}

function updateGraphRunningClass() {
  if (typeof graph !== 'undefined' && graph && graph.refreshRunning) {
    graph.refreshRunning();
  }
}

function renderGraphNodeSelection(d) {
  const titleEl = document.getElementById('side-step-title');
  const replayEl = document.getElementById('side-replay');
  const infoEl = document.getElementById('side-selection');
  const rows = [];
  const stepNum = d.step ?? d.firstStep ?? d.lastStep;
  const title = stepNum != null ? `Step #${stepNum}` : (d.label || d.fullUrl || d.id);
  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">level</span> <span class="v">${escHtml(d.type || '—')}</span></span></div>`);
  if (d.host)        rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">host</span> <span class="v">${escHtml(d.host)}</span></span></div>`);
  if (d.path)        rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">path</span> <span class="v">${escHtml(d.path || '/')}</span></span></div>`);
  if (d.size)        rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">size</span> <span class="v">${escHtml(d.size)}</span></span></div>`);
  if (d.scroll)      rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">scroll</span> <span class="v">${escHtml(d.scroll)}</span></span></div>`);
  if (d.actionName)  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">action</span> <span class="v">${escHtml(d.actionName)}</span></span></div>`);
  if (d.argsText)    rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">args</span> <span class="v">${escHtml(d.argsText)}</span></span></div>`);
  if (d.actionStepCount != null) rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">total steps</span> <span class="v">${d.actionStepCount}</span></span></div>`);
  if (d.visits != null)        rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">visits</span> <span class="v">${d.visits}</span></span></div>`);
  if (d.viewportCount != null) rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">viewports</span> <span class="v">${d.viewportCount}</span></span></div>`);
  if (d.actionCount != null)   rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">unique actions</span> <span class="v">${d.actionCount}</span></span></div>`);
  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">first step</span> <span class="v">#${d.firstStep ?? d.step ?? '—'}</span></span></div>`);
  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">last step</span> <span class="v">#${d.lastStep ?? d.step ?? '—'}</span></span></div>`);
  if (d.drillable)   rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">tip</span> <span class="v">double-click to drill in</span></span></div>`);

  if (titleEl) {
    titleEl.className = 'side-step-title';
    titleEl.textContent = title;
  }
  const replayBody = renderActionArtifacts(d.artifacts) + renderActionPreviewGallery(d.actionPreviews);
  if (replayEl) {
    replayEl.innerHTML = replayBody || '<div class="side-empty">no replay artifacts.</div>';
    hydrateNoopEvidence(replayEl);
  }
  if (infoEl) {
    infoEl.innerHTML = rows.length ? rows.join('') : '<div class="side-empty">no info.</div>';
  }
  renderRightPanelAuxiliarySections(d.llmInference, d.artifacts);
}

function renderSelection(d) {
  const titleEl = document.getElementById('side-step-title');
  const replayEl = document.getElementById('side-replay');
  const infoEl = document.getElementById('side-selection');
  if (!d) {
    if (titleEl) {
      titleEl.className = 'side-step-title side-empty';
      titleEl.textContent = 'no action step selected.';
    }
    if (replayEl) replayEl.innerHTML = '<div class="side-empty">no action step selected.</div>';
    if (infoEl) infoEl.innerHTML = '<div class="side-empty">no action step selected.</div>';
    renderRightPanelAuxiliarySections(null, null);
    return;
  }
  if (d.type === 'action') {
    if (typeof renderActionGroupAdditionalInfo === 'function') {
      renderActionGroupAdditionalInfo(d);
      return;
    }
  }
  renderGraphNodeSelection(d);
}

function scheduleGraphFit(delay = 30) {
  if (typeof graph === 'undefined' || !graph || !graph.fitToNodes) return;
  setTimeout(() => {
    if (!isGraphViewActive()) return;
    graph.fitToNodes();
  }, delay);
}

function setGraphDrilldown(next) {
  clearGraphDrillAnchor();
  graphDrilldown = next;
  updateGraph();
  scheduleGraphFit();
}
