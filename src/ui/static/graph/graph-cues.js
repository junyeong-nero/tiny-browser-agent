function truncateLabel(value, max = 28) {
  const s = String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  if (!s) return '';
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function refDescriptor(values) {
  if (values.ref_name) return `“${truncateLabel(values.ref_name)}”`;
  if (values.ref != null && values.ref !== '') return `ref ${values.ref}`;
  return 'element';
}

function textDescriptor(values) {
  const t = truncateLabel(values.text, 24);
  return t ? `“${t}”` : '';
}

function actionLabel(actionName, args) {
  const values = args || {};
  const ref = refDescriptor(values);
  const text = textDescriptor(values);
  if (actionName === 'navigate') return `Open ${truncateLabel(values.url || 'page', 40)}`;
  if (actionName === 'search') return 'Open search page';
  if (actionName === 'open_web_browser') return 'Open browser';
  if (actionName === 'observe_page') return 'Observe page';
  if (actionName === 'go_back') return 'Go back';
  if (actionName === 'go_forward') return 'Go forward';
  if (actionName === 'reload_page') return 'Reload page';
  if (actionName === 'click_at') return `Click at (${values.x}, ${values.y})`;
  if (actionName === 'click_by_ref') return `Click ${ref}`;
  if (actionName === 'hover_at') return `Hover at (${values.x}, ${values.y})`;
  if (actionName === 'type_text_at') return text ? `Type ${text} at (${values.x}, ${values.y})` : `Type at (${values.x}, ${values.y})`;
  if (actionName === 'type_by_ref') return text ? `Type ${text} → ${ref}` : `Type into ${ref}`;
  if (actionName === 'hover_by_ref') return `Hover ${ref}`;
  if (actionName === 'scroll_by_ref') return `Scroll ${values.direction || 'area'} on ${ref}`;
  if (actionName === 'check_by_ref') return `Check ${ref}`;
  if (actionName === 'wait_for_ref') return `Wait for ${ref}`;
  if (actionName === 'key_combination') return `Press ${Array.isArray(values.keys) ? values.keys.join(' + ') : values.keys || 'keys'}`;
  if (actionName === 'scroll_document') return `Scroll ${values.direction || 'page'}`;
  if (actionName === 'scroll_at') return `Scroll ${values.direction || 'area'}`;
  if (actionName === 'wait_5_seconds') return 'Wait for page';
  if (actionName === 'drag_and_drop') return 'Drag and drop';
  return String(actionName || 'Action').replace(/_/g, ' ');
}

function stableActionValue(value) {
  if (Array.isArray(value)) return value.map(stableActionValue);
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((acc, key) => {
      acc[key] = stableActionValue(value[key]);
      return acc;
    }, {});
  }
  return value;
}

function actionSignature(actionName, args) {
  return `${actionName}|${JSON.stringify(stableActionValue(args || {}))}`;
}

function actionStepCountForAction(action) {
  if (!action) return 0;
  if (Array.isArray(action.stepIds) && action.stepIds.length) return action.stepIds.length;
  return Number.isFinite(action.visits) ? action.visits : 0;
}

function actionStepCountForActionIds(actionIds) {
  return Array.from(actionIds || []).reduce((total, actionId) => {
    return total + actionStepCountForAction(trajectoryActions.get(actionId));
  }, 0);
}

// Outline §F2 motif-candidate cue types. `repeated` and `cycle` apply to every
// layer; `noop` is action-only; `deadEnd` requires P3 outcome metadata and
// applies to whichever layer's terminal node matches the failed terminal step.
const MOTIF_CUE_TYPES = ['cycle', 'repeated', 'noop', 'deadEnd'];

// Outline §S2 badge principle: own-layer cues that already have a dedicated
// visual channel must NOT duplicate into the badge. Dead-end and no-op own cues
// share the cue-ring stroke channel; badges summarize only collapsed lower-layer
// cues. The priority below chooses the dominant glyph / color when multiple
// descendant cue types are present.
const ROLLUP_CUE_PRIORITY = ['deadEnd', 'cycle', 'noop', 'repeated'];
const CUE_GLYPH = { cycle: '↻', deadEnd: '■', noop: '⊘', repeated: '×' };

function dominantRollupCueType(d) {
  if (!d || !d.rollupBreakdown) return null;
  for (const cueType of ROLLUP_CUE_PRIORITY) {
    if (d.rollupBreakdown[cueType] > 0) return cueType;
  }
  return null;
}

function ownCueRingType(d) {
  if (!d || !d.ownCues) return null;
  if (d.ownCues.deadEnd) return 'deadEnd';
  if (d.ownCues.noop) return 'noop';
  return null;
}

function nodeVisitCount(type, node) {
  if (type === 'action') {
    if (Number.isFinite(node.execCount) && node.execCount > 0) return node.execCount;
    if (Array.isArray(node.stepIds)) return node.stepIds.length;
  }
  return Number.isFinite(node.visits) ? node.visits : 0;
}

function isDeadEndCandidate(type, node, outcome) {
  if (!outcome || outcome.taskSuccess !== false || !outcome.terminalStepId) return false;
  const lastStep = node.lastStep != null ? String(node.lastStep) : null;
  return lastStep === outcome.terminalStepId;
}

function computeOwnCues(type, node, cyclicSet, outcome) {
  const cycle = !!(cyclicSet && cyclicSet.has(node.id));
  const repeated = nodeVisitCount(type, node) >= 2;
  const noop = type === 'action' && noopFlag(node);
  const deadEnd = isDeadEndCandidate(type, node, outcome);
  const anyRed = cycle || noop || deadEnd;
  return {
    cycle, repeated, noop, deadEnd,
    severity: anyRed ? 'red' : (repeated ? 'amber' : 'none'),
  };
}

function buildCueContext() {
  const outcome = trajectoryOutcome;

  const urlIds = new Set(Array.from(trajectoryNodes.keys()));
  const urlCyclic = computeCyclicNodes(buildSequentialLinks(urlSequence, urlIds, null));

  const viewportCyclicByUrl = new Map();
  for (const url of trajectoryNodes.values()) {
    const ids = new Set(url.viewportIds || []);
    const links = buildSequentialLinks(url.viewportSequence || [], ids, null);
    viewportCyclicByUrl.set(url.id, computeCyclicNodes(links));
  }
  const actionCyclicByViewport = new Map();
  for (const vp of trajectoryViewports.values()) {
    const ids = new Set(vp.actionIds || []);
    const links = buildSequentialLinks(vp.actionSequence || [], ids, null, true);
    actionCyclicByViewport.set(vp.id, computeCyclicNodes(links));
  }

  const ownCuesById = new Map();
  for (const url of trajectoryNodes.values()) {
    ownCuesById.set(url.id, computeOwnCues('url', url, urlCyclic, outcome));
  }
  for (const vp of trajectoryViewports.values()) {
    ownCuesById.set(vp.id, computeOwnCues('viewport', vp, viewportCyclicByUrl.get(vp.urlId), outcome));
  }
  for (const action of trajectoryActions.values()) {
    ownCuesById.set(action.id, computeOwnCues('action', action, actionCyclicByViewport.get(action.viewportId), outcome));
  }
  return { ownCuesById };
}

function rollupCueFor(type, scope, context) {
  const breakdown = { cycle: 0, repeated: 0, noop: 0, deadEnd: 0 };
  let count = 0;
  const tally = (id) => {
    const cues = context.ownCuesById.get(id);
    if (!cues) return;
    for (const cueType of MOTIF_CUE_TYPES) {
      if (cues[cueType]) {
        breakdown[cueType] += 1;
        count += 1;
      }
    }
  };
  if (type === 'url') {
    for (const vpId of scope.viewportIds || []) tally(vpId);
    for (const actId of scope.actionIds || []) tally(actId);
  } else if (type === 'viewport') {
    for (const actId of scope.actionIds || []) tally(actId);
  }
  return { rollupCount: count, rollupSeverity: count > 0 ? 'red' : 'none', rollupBreakdown: breakdown };
}
