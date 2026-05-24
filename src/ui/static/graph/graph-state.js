// Trajectory: Map<urlKey, {key, fullUrl, host, path, parent, children:Set, visits, firstStep, lastStep}>
let trajectoryNodes = new Map();
let trajectoryRoots = [];
let trajectoryLastKey = null;
let trajectoryCurrentKey = null;
let trajectoryCurrentViewportId = null;
let trajectoryCurrentActionId = null;
let activeGraphStepId = null;
let graphRenderDirty = false;

// ── Hierarchical graph state ────────────────────────────
// URL → viewport → action. Each level preserves chronological DAG edges;
// clicking a URL narrows to its viewport states, then clicking a viewport
// narrows to its action steps.
const trajectoryEdges = new Map(); // key: "src|dst" → {source, target, count}
const trajectoryViewports = new Map(); // id → viewport node
const trajectoryActions = new Map(); // id → action node
let actionNodeIdByStep = new Map();
let urlSequence = [];
let graphDrilldown = { level: 'url', urlId: null, viewportId: null };
let graphDrillAnchor = null;
let actionSequence = 0;
// Tracks the most-recently-observed post-action browser state so that the
// next step can compute (urlEq ∧ viewportEq ∧ ariaEq) → no-op.
let trajectoryLastSnapshot = null;
// Populated by P3 (task lifecycle event). dead-end / dead-action cues are
// gated on this being non-null + taskSuccess === false.
let trajectoryOutcome = null;

function setTrajectoryOutcome(outcome) {
  if (!outcome) { trajectoryOutcome = null; return; }
  trajectoryOutcome = {
    taskSuccess: !!outcome.taskSuccess,
    terminalStepId: outcome.terminalStepId != null ? String(outcome.terminalStepId) : null,
  };
  scheduleGraphUpdate();
}
const GRAPH_NODE_LABEL_MAX_CHARS = 28;

function resetTrajectoryGraphState() {
  trajectoryNodes = new Map();
  trajectoryRoots = [];
  trajectoryLastKey = null;
  trajectoryCurrentKey = null;
  trajectoryCurrentViewportId = null;
  trajectoryCurrentActionId = null;
  trajectoryEdges.clear();
  trajectoryViewports.clear();
  trajectoryActions.clear();
  actionNodeIdByStep.clear();
  urlSequence.length = 0;
  graphDrilldown = { level: 'url', urlId: null, viewportId: null };
  graphDrillAnchor = null;
  actionSequence = 0;
  activeGraphStepId = null;
  trajectoryLastSnapshot = null;
  trajectoryOutcome = null;
}

// Normalize an ARIA snapshot for structural comparison. Strips bracketed [ref]
// ids, collapses whitespace, and masks long digit runs that change between
// otherwise-identical snapshots (timestamps, counters). Intentionally cheap —
// similarity-aware matching is future work per docs/outline.md.
function ariaDiffSignature(text) {
  if (text == null) return '';
  let s = String(text);
  s = s.replace(/\[ref=[^\]]*\]/g, '');
  s = s.replace(/\[\s*\d+\s*\]/g, '');
  s = s.replace(/\b\d{3,}\b/g, '#');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

// True only after the evidence gate proves DOM, ARIA, and screenshot diffs are
// all under K. Until the async gate resolves, no-op badges stay hidden.
function noopFlag(actionNode) {
  return !!(actionNode && actionNode.noopEvidenceStatus === 'pass');
}

function rememberGraphDrillAnchor(d, nextDrilldown) {
  if (!d || !Number.isFinite(d.x) || !Number.isFinite(d.y)) {
    graphDrillAnchor = null;
    return;
  }
  graphDrillAnchor = {
    id: d.id,
    type: d.type || null,
    label: d.label || d.host || d.actionName || d.id,
    x: d.x,
    y: d.y,
    fromLevel: graphDrilldown.level,
    toLevel: nextDrilldown && nextDrilldown.level,
  };
}

function clearGraphDrillAnchor() {
  graphDrillAnchor = null;
}

function setGraphRunningStep(stepId) {
  activeGraphStepId = stepId != null ? String(stepId) : null;
  updateGraphRunningClass();
}

function clearGraphRunningStep(stepId) {
  if (stepId == null || (activeGraphStepId != null && String(activeGraphStepId) === String(stepId))) {
    activeGraphStepId = null;
    updateGraphRunningClass();
  }
}


function isRunningGraphNode(d) {
  if (activeGraphStepId == null || !d) return false;
  if (Array.isArray(d.stepIds)) return d.stepIds.map(String).includes(String(activeGraphStepId));
  if (d.step != null) return String(d.step) === String(activeGraphStepId);
  if (d.firstStep == null || d.lastStep == null) return false;
  const activeStep = Number(activeGraphStepId);
  return Number(d.firstStep) <= activeStep && activeStep <= Number(d.lastStep);
}
