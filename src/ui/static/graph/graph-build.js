function recordNavigation(url, stepId) {
  if (!url || url === 'about:blank') return null;
  const { key, host, path, full } = parseUrlParts(url);

  let node = trajectoryNodes.get(key);
  if (!node) {
    node = {
      id: key, fullUrl: full, host, path,
      parent: trajectoryLastKey,
      childrenKeys: new Set(),
      viewportIds: new Set(),
      actionIds: new Set(),
      viewportSequence: [],
      visits: 0,
      firstStep: stepId,
      lastStep: stepId,
    };
    trajectoryNodes.set(key, node);
    if (!trajectoryLastKey) trajectoryRoots.push(key);
  }
  node.visits += 1;
  node.lastStep = stepId;
  if (node.fullUrl !== full) node.fullUrl = full;

  if (trajectoryLastKey && trajectoryLastKey !== key) {
    const parentNode = trajectoryNodes.get(trajectoryLastKey);
    if (parentNode) parentNode.childrenKeys.add(key);
    const edgeKey = trajectoryLastKey + '|' + key;
    const edge = trajectoryEdges.get(edgeKey);
    if (edge) edge.count += 1;
    else trajectoryEdges.set(edgeKey, { source: trajectoryLastKey, target: key, count: 1 });
  }

  trajectoryLastKey = key;
  urlSequence.push(key);
  trajectoryCurrentKey = key;
  return node;
}

function recordActionExecution(ev) {
  if (!ev || !ev.env_state || !ev.env_state.url) return;
  const urlNode = recordNavigation(ev.env_state.url, ev.step_id);
  if (!urlNode) return;

  const viewport = viewportInfoFromArtifacts(ev.artifacts);
  const viewportId = `viewport|${urlNode.id}|${viewport.key}`;
  let viewportNode = trajectoryViewports.get(viewportId);
  if (!viewportNode) {
    viewportNode = {
      id: viewportId,
      urlId: urlNode.id,
      label: viewportLabel(viewport, ev.step_id),
      type: 'viewport',
      size: viewport.size,
      scroll: viewport.scroll,
      screenshot: viewport.screenshot,
      artifactStep: viewport.artifactStep,
      visits: 0,
      firstStep: ev.step_id,
      lastStep: ev.step_id,
      actionIds: new Set(),
      actionSequence: [],
    };
    trajectoryViewports.set(viewportId, viewportNode);
    urlNode.viewportIds.add(viewportId);
  }
  viewportNode.visits += 1;
  viewportNode.lastStep = ev.step_id;
  if (viewport.screenshot) viewportNode.screenshot = viewport.screenshot;
  if (viewport.artifactStep != null) viewportNode.artifactStep = viewport.artifactStep;
  urlNode.viewportSequence.push(viewportId);
  trajectoryCurrentViewportId = viewportId;

  const action = ev.action || {};
  const actionName = action.name || 'action';
  const actionArgs = action.args || {};
  const stepIdKey = ev.step_id != null ? String(ev.step_id) : null;
  const actionId = `action|${viewportId}|${actionSignature(actionName, actionArgs)}`;
  const postAriaText = (ev.artifacts && ev.artifacts.aria_snapshot) || '';
  const postAriaSig = ariaDiffSignature(postAriaText);
  const preSnap = trajectoryLastSnapshot;
  const preAriaText = preSnap ? (preSnap.ariaText || '') : '';
  let actionNode = trajectoryActions.get(actionId);
  if (!actionNode) {
    actionNode = {
      id: actionId,
      urlId: urlNode.id,
      viewportId,
      label: actionLabel(actionName, actionArgs),
      type: 'action',
      actionName,
      args: actionArgs,
      stepIds: [],
      step: ev.step_id,
      order: actionSequence++,
      fullUrl: urlNode.fullUrl,
      artifacts: ev.artifacts || null,
      actionGifPath: ev.artifacts && (ev.artifacts.action_clip_gif_path || ev.artifacts.action_gif_path),
      beforeScreenshotPath: ev.artifacts && ev.artifacts.before_screenshot_path,
      afterScreenshotPath: ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path),
      videoPath: ev.artifacts && ev.artifacts.video_path,
      llmInference: llmInferenceForStep(ev.step_id),
      visits: 0,
      firstStep: ev.step_id,
      lastStep: ev.step_id,
      preAriaSig: preSnap ? preSnap.ariaSig : null,
      postAriaSig,
      preAriaText,
      postAriaText,
      noopCount: 0,
      noopEvidenceStatus: 'unknown',
      noopEvidence: null,
      execCount: 0,
    };
    trajectoryActions.set(actionId, actionNode);
    viewportNode.actionIds.add(actionId);
    urlNode.actionIds.add(actionId);
  }
  if (stepIdKey != null && !actionNode.stepIds.includes(stepIdKey)) {
    actionNode.stepIds.push(stepIdKey);
    actionNodeIdByStep.set(stepIdKey, actionId);
  }
  actionNode.step = ev.step_id;
  actionNode.lastStep = ev.step_id;
  actionNode.visits += 1;
  actionNode.fullUrl = urlNode.fullUrl;
  actionNode.artifacts = ev.artifacts || actionNode.artifacts;
  actionNode.actionGifPath = (ev.artifacts && (ev.artifacts.action_clip_gif_path || ev.artifacts.action_gif_path)) || actionNode.actionGifPath;
  actionNode.beforeScreenshotPath = (ev.artifacts && ev.artifacts.before_screenshot_path) || actionNode.beforeScreenshotPath;
  actionNode.afterScreenshotPath = (ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path)) || actionNode.afterScreenshotPath;
  actionNode.videoPath = (ev.artifacts && ev.artifacts.video_path) || actionNode.videoPath;
  actionNode.llmInference = llmInferenceForStep(ev.step_id) || actionNode.llmInference;
  actionNode.execCount = (actionNode.execCount || 0) + 1;
  actionNode.postAriaSig = postAriaSig;
  actionNode.postAriaText = postAriaText;
  if (actionNode.preAriaSig == null && preSnap) actionNode.preAriaSig = preSnap.ariaSig;
  if (!actionNode.preAriaText && preAriaText) actionNode.preAriaText = preAriaText;
  if (actionNode.artifacts) {
    primeNoopEvidenceForAction(actionNode);
  }
  viewportNode.actionSequence.push(actionId);
  trajectoryCurrentActionId = actionId;
  trajectoryLastSnapshot = {
    urlKey: urlNode.id,
    viewportKey: viewport.key,
    ariaSig: postAriaSig,
    ariaText: postAriaText,
    stepId: ev.step_id,
  };
  scheduleGraphUpdate();
}

function firstAllowedInSequence(sequence, allowedIds) {
  for (const id of sequence || []) {
    if (allowedIds.has(id)) return id;
  }
  return null;
}

function lastAllowedInSequence(sequence, allowedIds) {
  const seq = sequence || [];
  for (let i = seq.length - 1; i >= 0; i--) {
    if (allowedIds.has(seq[i])) return seq[i];
  }
  return null;
}

function annotateLevelEndpoints(childNodes, sequence) {
  const ids = new Set(childNodes.map(n => n.id));
  const firstIndexById = new Map();
  (sequence || []).forEach((id, index) => {
    if (ids.has(id) && !firstIndexById.has(id)) firstIndexById.set(id, index);
  });
  const startId = firstAllowedInSequence(sequence, ids);
  const endId = lastAllowedInSequence(sequence, ids);
  childNodes.forEach(n => {
    n.isStart = n.id === startId;
    n.isEnd = n.id === endId;
    n._sequenceIndex = firstIndexById.has(n.id) ? firstIndexById.get(n.id) : Number.MAX_SAFE_INTEGER;
  });
}

function buildSequentialLinks(sequence, allowedIds, rootId = null, allowSelfLoops = false) {
  const edges = new Map();
  let previous = rootId;
  for (const id of sequence || []) {
    if (!allowedIds.has(id)) continue;
    if (previous && (allowSelfLoops || previous !== id)) {
      const edgeKey = `${previous}|${id}`;
      const edge = edges.get(edgeKey);
      if (edge) edge.count += 1;
      else edges.set(edgeKey, { source: previous, target: id, count: 1 });
    }
    previous = id;
  }
  return Array.from(edges.values());
}

function edgeEndpointId(endpoint) {
  return endpoint && typeof endpoint === 'object' ? endpoint.id : endpoint;
}

// Tarjan SCC over the link list. Returns the Set of node ids that participate
// in a non-trivial strongly-connected component (size ≥ 2). Reused by both
// edge highlighting and cue computation per outline §F2 State/Action Loop.
function computeCyclicNodes(links) {
  const adjacency = new Map();
  for (const link of links || []) {
    const source = edgeEndpointId(link.source);
    const target = edgeEndpointId(link.target);
    if (!source || !target) continue;
    if (!adjacency.has(source)) adjacency.set(source, []);
    if (!adjacency.has(target)) adjacency.set(target, []);
    adjacency.get(source).push(target);
  }

  const indexById = new Map();
  const lowlinkById = new Map();
  const stack = [];
  const onStack = new Set();
  const cyclicNodes = new Set();
  let index = 0;

  function strongConnect(id) {
    indexById.set(id, index);
    lowlinkById.set(id, index);
    index += 1;
    stack.push(id);
    onStack.add(id);

    for (const target of adjacency.get(id) || []) {
      if (!indexById.has(target)) {
        strongConnect(target);
        lowlinkById.set(id, Math.min(lowlinkById.get(id), lowlinkById.get(target)));
      } else if (onStack.has(target)) {
        lowlinkById.set(id, Math.min(lowlinkById.get(id), indexById.get(target)));
      }
    }

    if (lowlinkById.get(id) !== indexById.get(id)) return;
    const component = [];
    let node = null;
    do {
      node = stack.pop();
      onStack.delete(node);
      component.push(node);
    } while (node !== id);

    if (component.length > 1) {
      component.forEach(componentNode => cyclicNodes.add(componentNode));
    }
  }

  Array.from(adjacency.keys()).forEach(id => {
    if (!indexById.has(id)) strongConnect(id);
  });

  return cyclicNodes;
}

function detectCycleEdges(links) {
  const cyclicNodes = computeCyclicNodes(links);
  return (links || []).map(link => {
    const source = edgeEndpointId(link.source);
    const target = edgeEndpointId(link.target);
    const isCycleEdge = !!source && !!target && (source === target || (cyclicNodes.has(source) && cyclicNodes.has(target)));
    return { ...link, isCycleEdge };
  });
}

function attachCueFields(type, src, _sequence, context) {
  const own = context.ownCuesById.get(src.id) || {
    cycle: false, repeated: false, noop: false, deadEnd: false, severity: 'none',
  };
  const rollup = rollupCueFor(type, src, context);
  const rollupCount = rollup.rollupCount;
  // Badge principle: badgeCount is lower-layer rollup only. Own-layer cues are
  // already visible via node size/fill, edge highlights, terminal outline, or
  // action detail evidence, so they must not inflate the badge.
  const badgeCount = rollupCount;
  return {
    ownCues: own,
    ownSeverity: own.severity,
    rollupCount,
    rollupSeverity: rollup.rollupSeverity,
    rollupBreakdown: rollup.rollupBreakdown,
    badgeCount,
  };
}

function buildTrajectoryGraphData() {
  if (graphDrilldown.level === 'viewport' && graphDrilldown.urlId) {
    return buildViewportGraphData(graphDrilldown.urlId);
  }
  if (graphDrilldown.level === 'action' && graphDrilldown.viewportId) {
    return buildActionGraphData(graphDrilldown.viewportId);
  }
  return buildUrlGraphData();
}

function buildUrlGraphData() {
  const cueContext = buildCueContext();
  const nodes = Array.from(trajectoryNodes.values()).map(src => ({
    id: src.id,
    label: trajectoryLabelFor(src),
    type: 'url',
    fullUrl: src.fullUrl,
    host: src.host,
    path: src.path,
    visits: src.visits,
    firstStep: src.firstStep,
    lastStep: src.lastStep,
    viewportCount: src.viewportIds ? src.viewportIds.size : 0,
    actionStepCount: actionStepCountForActionIds(src.actionIds),
    actionCount: src.actionIds ? src.actionIds.size : 0,
    actionPreviews: collectActionPreviewArtifacts(src.actionIds),
    llmInference: llmInferenceForStep(src.lastStep),
    isRoot: trajectoryRoots.includes(src.id),
    isCurrent: src.id === trajectoryCurrentKey,
    drillable: !!(src.viewportIds && src.viewportIds.size),
    ...attachCueFields('url', src, urlSequence, cueContext), // computeOwnCues + rollupCueFor → badgeCount
  }));
  const idSet = new Set(nodes.map(n => n.id));
  annotateLevelEndpoints(nodes, urlSequence);
  const links = detectCycleEdges(Array.from(trajectoryEdges.values())
    .filter(e => idSet.has(e.source) && idSet.has(e.target))
    .map(e => ({ source: e.source, target: e.target, count: e.count })));
  return { nodes, links, mode: 'url', breadcrumb: [] };
}

function buildViewportGraphData(urlId) {
  const urlNode = trajectoryNodes.get(urlId);
  if (!urlNode) {
    graphDrilldown = { level: 'url', urlId: null, viewportId: null };
    return buildUrlGraphData();
  }
  const cueContext = buildCueContext();
  const parentLabel = trajectoryLabelFor(urlNode);
  const viewports = Array.from(urlNode.viewportIds || [])
    .map(id => trajectoryViewports.get(id))
    .filter(Boolean)
    .map(vp => ({
      id: vp.id,
      label: vp.label,
      type: 'viewport',
      urlId: vp.urlId,
      size: vp.size,
      scroll: vp.scroll,
      screenshot: vp.screenshot,
      visits: vp.visits,
      firstStep: vp.firstStep,
      lastStep: vp.lastStep,
      actionStepCount: actionStepCountForActionIds(vp.actionIds),
      actionCount: vp.actionIds.size,
      actionPreviews: collectActionPreviewArtifacts(vp.actionIds),
      llmInference: llmInferenceForStep(vp.lastStep),
      isCurrent: vp.id === trajectoryCurrentViewportId,
      drillable: !!vp.actionIds.size,
      ...attachCueFields('viewport', vp, urlNode.viewportSequence, cueContext), // computeOwnCues + rollupCueFor → badgeCount
    }));
  const viewportIds = new Set(viewports.map(vp => vp.id));
  annotateLevelEndpoints(viewports, urlNode.viewportSequence);
  const links = detectCycleEdges(buildSequentialLinks(urlNode.viewportSequence, viewportIds, null));
  return {
    nodes: viewports,
    links,
    mode: 'viewport',
    breadcrumb: [{ label: 'URLs', level: 'url' }],
    parentLabel,
  };
}

function buildActionGraphData(viewportId) {
  const viewportNode = trajectoryViewports.get(viewportId);
  if (!viewportNode) {
    graphDrilldown = { level: 'url', urlId: null, viewportId: null };
    return buildUrlGraphData();
  }
  const urlNode = trajectoryNodes.get(viewportNode.urlId);
  const cueContext = buildCueContext();
  const parentLabel = viewportNode.label;
  const actions = Array.from(viewportNode.actionIds || [])
    .map(id => trajectoryActions.get(id))
    .filter(Boolean)
    .sort((a, b) => (a.firstStep - b.firstStep) || (a.order - b.order))
    .map(action => ({
      ...action,
      actionStepCount: actionStepCountForAction(action),
      argsText: formatArgs(action.args || {}),
      llmInference: action.llmInference || llmInferenceForStep(action.lastStep || action.step),
      isCurrent: action.id === trajectoryCurrentActionId,
      ...attachCueFields('action', action, viewportNode.actionSequence, cueContext), // computeOwnCues + rollupCueFor → badgeCount
    }));
  const actionIds = new Set(actions.map(action => action.id));
  annotateLevelEndpoints(actions, viewportNode.actionSequence);
  const links = detectCycleEdges(buildSequentialLinks(viewportNode.actionSequence, actionIds, null, true));
  const crumbs = [{ label: 'URLs', level: 'url' }];
  if (urlNode) crumbs.push({ label: trajectoryLabelFor(urlNode), level: 'viewport', urlId: urlNode.id });
  return { nodes: actions, links, mode: 'action', breadcrumb: crumbs, parentLabel };
}

function trajectoryLabelFor(n) {
  const p = n.path && n.path !== '/' ? n.path : '';
  const short = (n.host || '') + (p ? (p.length > 18 ? p.slice(0, 17) + '…' : p) : '');
  return short || n.id;
}

function compactGraphNodeLabel(label, maxChars = GRAPH_NODE_LABEL_MAX_CHARS) {
  const text = String(label || '');
  if (maxChars <= 1) return text.slice(0, maxChars);
  return text.length <= maxChars ? text : text.slice(0, maxChars - 1) + '…';
}

function displayGraphNodeLabel(d) {
  return compactGraphNodeLabel((d && (d.label || d.id)) || '');
}

function selectedGraphData() {
  return buildTrajectoryGraphData();
}

function drillGraphNode(d) {
  if (!d || !d.drillable) return;
  let nextDrilldown = null;
  if (d.type === 'url') {
    nextDrilldown = { level: 'viewport', urlId: d.id, viewportId: null };
  } else if (d.type === 'viewport') {
    nextDrilldown = { level: 'action', urlId: d.urlId, viewportId: d.id };
  }
  if (!nextDrilldown) return;
  clearGraphDrillAnchor();
  graphDrilldown = nextDrilldown;
  selectedNodeId = null;
  selectedNodeData = null;
  renderSelection(null);
  updateGraph();
  scheduleGraphFit();
}
