// Trajectory: Map<urlKey, {key, fullUrl, host, path, parent, children:Set, visits, firstStep, lastStep}>
let trajectoryNodes = new Map();
let trajectoryRoots = [];
let trajectoryLastKey = null;
let trajectoryCurrentKey = null;
let trajectoryCurrentViewportId = null;
let trajectoryCurrentActionId = null;
let activeGraphStepId = null;

// ── Hierarchical graph state ────────────────────────────
// URL → viewport → action. Each level preserves chronological DAG edges;
// clicking a URL narrows to its viewport states, then clicking a viewport
// narrows to its action steps.
const trajectoryEdges = new Map(); // key: "src|dst" → {source, target, count}
const trajectoryViewports = new Map(); // id → viewport node
const trajectoryActions = new Map(); // id → action node
let actionNodeIdByStep = new Map();
let graphDrilldown = { level: 'url', urlId: null, viewportId: null };
let graphDrillAnchor = null;
let actionSequence = 0;

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
  graphDrilldown = { level: 'url', urlId: null, viewportId: null };
  graphDrillAnchor = null;
  actionSequence = 0;
  activeGraphStepId = null;
}

function rememberGraphDrillAnchor(d) {
  if (!d || !Number.isFinite(d.x) || !Number.isFinite(d.y)) {
    graphDrillAnchor = null;
    return;
  }
  graphDrillAnchor = { id: d.id, x: d.x, y: d.y };
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

function parseUrlParts(url) {
  try {
    const u = new URL(url);
    const host = u.host || u.protocol.replace(':', '');
    const path = (u.pathname || '/') + (u.search || '');
    return { key: u.origin + u.pathname, host, path, full: url };
  } catch (_) {
    return { key: url, host: '', path: url, full: url };
  }
}

function stateGraphLeaf(artifacts, leafId) {
  const nodes = artifacts && artifacts.state_graph && artifacts.state_graph.nodes;
  if (!Array.isArray(nodes)) return null;
  return nodes.find(n => n && n.id === leafId) || null;
}

function viewportInfoFromArtifacts(artifacts) {
  const sizeLeaf = stateGraphLeaf(artifacts, 'viewport.size');
  const scrollLeaf = stateGraphLeaf(artifacts, 'viewport.scroll');
  const screenshotLeaf = stateGraphLeaf(artifacts, 'viewport.screenshot');
  const size = (sizeLeaf && (sizeLeaf.full_value || sizeLeaf.value)) || 'unknown size';
  const scroll = (scrollLeaf && (scrollLeaf.full_value || scrollLeaf.value)) || 'x=0, y=0';
  const screenshot = screenshotLeaf && (screenshotLeaf.full_value || screenshotLeaf.value);
  const artifactStep = artifacts && artifacts.step != null ? artifacts.step : null;
  return {
    key: `${size}|${scroll}`,
    size,
    scroll,
    screenshot: screenshot || '',
    artifactStep,
  };
}

function scrollLabel(scroll) {
  const match = String(scroll || '').match(/x=(\d+), y=(\d+)/);
  if (!match) return String(scroll || 'visible area');
  const x = Number(match[1]);
  const y = Number(match[2]);
  if (x === 0 && y === 0) return 'Top of page';
  if (x === 0) return `Scrolled ${y}px down`;
  if (y === 0) return `Scrolled ${x}px right`;
  return `Scrolled x=${x}, y=${y}`;
}

function viewportLabel(viewport, stepId) {
  const stepLabel = stepId != null ? `Screen #${stepId}` : 'Screen view';
  return `${stepLabel} · ${scrollLabel(viewport.scroll)}`;
}

function artifactPathName(path, expectedDir) {
  if (!path) return '';
  const parts = String(path).split('/').filter(Boolean);
  if (parts.length === 2 && parts[0] === expectedDir) return parts[1];
  return parts[parts.length - 1] || '';
}

function replayArtifactHref(path, expectedDir = 'history') {
  const sessionId = replayMode ? replaySessionId : liveSessionId;
  if (!sessionId || !path) return '';
  const name = artifactPathName(path, expectedDir);
  if (!name) return '';
  return `/sessions/${encodeURIComponent(sessionId)}/artifacts/${expectedDir}/${encodeURIComponent(name)}`;
}

function renderArtifactCard(label, href, kind = 'image') {
  if (!href) return '';
  const safeLabel = escHtml(label);
  const safeHref = escHtml(href);
  const media = kind === 'video'
    ? `<video controls preload="metadata" src="${safeHref}"></video>`
    : `<a target="_blank" rel="noreferrer" href="${safeHref}"><img src="${safeHref}" alt="${safeLabel} screenshot"></a>`;
  return `<div class="artifact-card"><div class="artifact-label">${safeLabel} · <a class="artifact-link" target="_blank" rel="noreferrer" href="${safeHref}">open</a></div>${media}</div>`;
}

function artifactCompareId(beforeHref, afterHref) {
  const raw = `${beforeHref || ''}|${afterHref || ''}`;
  let hash = 0;
  for (let i = 0; i < raw.length; i += 1) {
    hash = ((hash << 5) - hash + raw.charCodeAt(i)) | 0;
  }
  return `artifact-compare-${Math.abs(hash)}`;
}

function renderActionReplayCard(label, href) {
  if (!href) return '';
  const safeLabel = escHtml(label || 'Action replay');
  const safeHref = escHtml(href);
  return `<div class="artifact-primary"><div class="artifact-card"><div class="artifact-label">${safeLabel} · <a class="artifact-link" target="_blank" rel="noreferrer" href="${safeHref}">open</a></div><a target="_blank" rel="noreferrer" href="${safeHref}"><img src="${safeHref}" alt="${safeLabel}"></a></div></div>`;
}

function renderBeforeAfterCompare(beforeHref, afterHref) {
  if (!beforeHref && !afterHref) return '';
  if (!beforeHref || !afterHref) {
    const label = beforeHref ? 'Before screenshot' : 'After screenshot';
    return renderArtifactCard(label, beforeHref || afterHref);
  }
  const id = artifactCompareId(beforeHref, afterHref);
  const before = escHtml(beforeHref);
  const after = escHtml(afterHref);
  return `
    <div class="artifact-compare-control">
      <div class="artifact-compare-title">Compare · <a class="artifact-link" target="_blank" rel="noreferrer" href="${before}">open before</a> · <a class="artifact-link" target="_blank" rel="noreferrer" href="${after}">open after</a></div>
      <input id="${id}-before" name="${id}" type="radio" data-compare-mode="before" checked>
      <input id="${id}-after" name="${id}" type="radio" data-compare-mode="after">
      <input id="${id}-split" name="${id}" type="radio" data-compare-mode="split">
      <div class="artifact-compare-tabs">
        <label for="${id}-before">Before</label>
        <label for="${id}-after">After</label>
        <label for="${id}-split">Split</label>
      </div>
      <div class="artifact-compare-panels">
        <a class="artifact-compare-panel artifact-panel-before" target="_blank" rel="noreferrer" href="${before}"><img src="${before}" alt="Before screenshot"></a>
        <a class="artifact-compare-panel artifact-panel-after" target="_blank" rel="noreferrer" href="${after}"><img src="${after}" alt="After screenshot"></a>
        <div class="artifact-compare-panel artifact-panel-split">
          <div class="artifact-split">
            <figure><figcaption>Before</figcaption><a target="_blank" rel="noreferrer" href="${before}"><img src="${before}" alt="Before screenshot"></a></figure>
            <figure><figcaption>After</figcaption><a target="_blank" rel="noreferrer" href="${after}"><img src="${after}" alt="After screenshot"></a></figure>
          </div>
        </div>
      </div>
    </div>`;
}

function renderActionArtifacts(artifacts) {
  if (!artifacts) return '';
  const actionGif = replayArtifactHref(artifacts.action_clip_gif_path || artifacts.action_gif_path, 'history');
  const beforeShot = replayArtifactHref(artifacts.before_screenshot_path, 'history');
  const afterShot = replayArtifactHref(artifacts.after_screenshot_path || artifacts.screenshot_path, 'history');
  const video = replayArtifactHref(artifacts.video_path, 'video');
  const cards = [
    renderActionReplayCard('Action replay', actionGif),
    renderBeforeAfterCompare(beforeShot, afterShot),
  ].filter(Boolean);
  const videoCard = renderArtifactCard('session video', video, 'video');
  const names = [];
  if (artifacts.action_clip_gif_path || artifacts.action_gif_path) names.push(`gif=${escHtml(artifacts.action_clip_gif_path || artifacts.action_gif_path)}`);
  if (artifacts.before_screenshot_path) names.push(`before=${escHtml(artifacts.before_screenshot_path)}`);
  if (artifacts.after_screenshot_path || artifacts.screenshot_path) names.push(`after=${escHtml(artifacts.after_screenshot_path || artifacts.screenshot_path)}`);
  if (artifacts.video_path) names.push(`video=${escHtml(artifacts.video_path)}`);
  const pathDetails = names.length
    ? `<details class="artifact-paths"><summary>Technical paths</summary>${names.map(name => `<div class="bullet"><span class="dot">•</span><span><span class="v">${name}</span></span></div>`).join('')}</details>`
    : '';
  return (cards.length ? `<div class="artifact-compare">${cards.join('')}</div>` : '') + videoCard + pathDetails;
}

function actionPreviewArtifactsFor(action) {
  const artifacts = action && action.artifacts;
  if (!artifacts) return null;
  const previewPath = artifacts.action_clip_gif_path || artifacts.action_gif_path || artifacts.after_screenshot_path || artifacts.screenshot_path;
  if (!previewPath) return null;
  return {
    label: action.label || `#${action.step || ''} action`,
    path: previewPath,
    kind: (artifacts.action_clip_gif_path || artifacts.action_gif_path) ? 'gif' : 'image',
  };
}

function collectActionPreviewArtifacts(actionIds) {
  return Array.from(actionIds || [])
    .map(id => trajectoryActions.get(id))
    .filter(Boolean)
    .sort((a, b) => (a.step - b.step) || (a.order - b.order))
    .map(actionPreviewArtifactsFor)
    .filter(Boolean);
}

function renderActionPreviewGallery(previews) {
  if (!Array.isArray(previews) || !previews.length) return '';
  const cards = previews.map((preview, index) => {
    const href = replayArtifactHref(preview.path, 'history');
    const label = preview.label || `action ${index + 1}`;
    return renderArtifactCard(label, href);
  }).filter(Boolean);
  if (!cards.length) return '';
  return `<div class="bullet"><span class="dot">•</span><span><span class="k">child previews</span> <span class="v">${cards.length} action(s)</span></span></div>` +
    `<div class="artifact-gallery">${cards.join('')}</div>`;
}

function llmInferenceForStep(stepId) {
  if (stepId == null || typeof window.getLlmInferenceForStep !== 'function') return null;
  return window.getLlmInferenceForStep(stepId);
}

function formatRawJson(value) {
  if (value == null) return 'null';
  try {
    return JSON.stringify(value, null, 2);
  } catch (_) {
    return String(value);
  }
}

function renderLlmInferenceButton(inference) {
  if (!inference) return '';
  return `
    <details class="llm-raw-details">
      <summary class="llm-raw-button">View LLM raw context / response</summary>
      <div class="llm-raw-block">
        <div class="llm-raw-title">Raw context</div>
        <pre>${escHtml(formatRawJson(inference.rawContext))}</pre>
        <div class="llm-raw-title">Output response</div>
        <pre>${escHtml(formatRawJson(inference.rawResponse))}</pre>
      </div>
    </details>`;
}

function actionLabel(actionName, args) {
  const values = args || {};
  const refLabel = values.ref_name || values.ref;
  if (actionName === 'navigate') return `Open ${values.url || 'page'}`;
  if (actionName === 'search') return 'Open search page';
  if (actionName === 'open_web_browser') return 'Open browser';
  if (actionName === 'go_back') return 'Go back';
  if (actionName === 'go_forward') return 'Go forward';
  if (actionName === 'reload_page') return 'Reload page';
  if (actionName === 'click_at') return `Click at (${values.x}, ${values.y})`;
  if (actionName === 'click_by_ref') return `Click “${refLabel}”`;
  if (actionName === 'hover_at') return `Hover at (${values.x}, ${values.y})`;
  if (actionName === 'type_text_at') return 'Type text';
  if (actionName === 'type_by_ref') return `Type into “${refLabel}”`;
  if (actionName === 'hover_by_ref') return `Hover “${refLabel}”`;
  if (actionName === 'scroll_by_ref') return `Scroll ${values.direction || 'area'} on “${refLabel}”`;
  if (actionName === 'check_by_ref') return `Check “${refLabel}”`;
  if (actionName === 'wait_for_ref') return `Wait for “${refLabel}”`;
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
  viewportNode.actionSequence.push(actionId);
  trajectoryCurrentActionId = actionId;
  updateGraph();
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

function detectCycleEdges(links) {
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

  return (links || []).map(link => {
    const source = edgeEndpointId(link.source);
    const target = edgeEndpointId(link.target);
    const isCycleEdge = !!source && !!target && (source === target || (cyclicNodes.has(source) && cyclicNodes.has(target)));
    return { ...link, isCycleEdge };
  });
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
    actionCount: src.actionIds ? src.actionIds.size : 0,
    actionPreviews: collectActionPreviewArtifacts(src.actionIds),
    llmInference: llmInferenceForStep(src.lastStep),
    isRoot: trajectoryRoots.includes(src.id),
    isCurrent: src.id === trajectoryCurrentKey,
    drillable: !!(src.viewportIds && src.viewportIds.size),
  }));
  const idSet = new Set(nodes.map(n => n.id));
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
  const root = {
    id: urlNode.id,
    label: trajectoryLabelFor(urlNode),
    type: 'url',
    fullUrl: urlNode.fullUrl,
    host: urlNode.host,
    path: urlNode.path,
    visits: urlNode.visits,
    firstStep: urlNode.firstStep,
    lastStep: urlNode.lastStep,
    viewportCount: urlNode.viewportIds.size,
    actionCount: urlNode.actionIds.size,
    actionPreviews: collectActionPreviewArtifacts(urlNode.actionIds),
    isRoot: true,
    isCurrent: urlNode.id === trajectoryCurrentKey,
  };
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
      actionCount: vp.actionIds.size,
      actionPreviews: collectActionPreviewArtifacts(vp.actionIds),
      llmInference: llmInferenceForStep(vp.lastStep),
      isCurrent: vp.id === trajectoryCurrentViewportId,
      drillable: !!vp.actionIds.size,
    }));
  const viewportIds = new Set(viewports.map(vp => vp.id));
  const links = detectCycleEdges(buildSequentialLinks(urlNode.viewportSequence, viewportIds, root.id));
  return {
    nodes: [root, ...viewports],
    links,
    mode: 'viewport',
    breadcrumb: [{ label: 'URLs', level: 'url' }],
  };
}

function buildActionGraphData(viewportId) {
  const viewportNode = trajectoryViewports.get(viewportId);
  if (!viewportNode) {
    graphDrilldown = { level: 'url', urlId: null, viewportId: null };
    return buildUrlGraphData();
  }
  const urlNode = trajectoryNodes.get(viewportNode.urlId);
  const root = {
    id: viewportNode.id,
    label: viewportNode.label,
    type: 'viewport',
    urlId: viewportNode.urlId,
    size: viewportNode.size,
    scroll: viewportNode.scroll,
    screenshot: viewportNode.screenshot,
    visits: viewportNode.visits,
    firstStep: viewportNode.firstStep,
    lastStep: viewportNode.lastStep,
    actionCount: viewportNode.actionIds.size,
    actionPreviews: collectActionPreviewArtifacts(viewportNode.actionIds),
    llmInference: llmInferenceForStep(viewportNode.lastStep),
    isRoot: true,
    isCurrent: viewportNode.id === trajectoryCurrentViewportId,
  };
  const actions = Array.from(viewportNode.actionIds || [])
    .map(id => trajectoryActions.get(id))
    .filter(Boolean)
    .sort((a, b) => (a.firstStep - b.firstStep) || (a.order - b.order))
    .map(action => ({
      ...action,
      argsText: formatArgs(action.args || {}),
      llmInference: action.llmInference || llmInferenceForStep(action.lastStep || action.step),
      isCurrent: action.id === trajectoryCurrentActionId,
    }));
  const actionIds = new Set(actions.map(action => action.id));
  const links = detectCycleEdges(buildSequentialLinks(viewportNode.actionSequence, actionIds, root.id, true));
  const crumbs = [{ label: 'URLs', level: 'url' }];
  if (urlNode) crumbs.push({ label: trajectoryLabelFor(urlNode), level: 'viewport', urlId: urlNode.id });
  return { nodes: [root, ...actions], links, mode: 'action', breadcrumb: crumbs };
}

function trajectoryLabelFor(n) {
  const p = n.path && n.path !== '/' ? n.path : '';
  const short = (n.host || '') + (p ? (p.length > 18 ? p.slice(0, 17) + '…' : p) : '');
  return short || n.id;
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
  rememberGraphDrillAnchor(d);
  graphDrilldown = nextDrilldown;
  selectedNodeId = null;
  selectedNodeData = null;
  renderSelection(null);
  updateGraph();
}

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
  if (d.visits != null)        rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">visits</span> <span class="v">${d.visits}</span></span></div>`);
  if (d.viewportCount != null) rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">viewports</span> <span class="v">${d.viewportCount}</span></span></div>`);
  if (d.actionCount != null)   rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">actions</span> <span class="v">${d.actionCount}</span></span></div>`);
  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">first step</span> <span class="v">#${d.firstStep ?? d.step ?? '—'}</span></span></div>`);
  rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">last step</span> <span class="v">#${d.lastStep ?? d.step ?? '—'}</span></span></div>`);
  if (d.drillable)   rows.push(`<div class="bullet"><span class="dot">•</span><span><span class="k">tip</span> <span class="v">double-click to drill in</span></span></div>`);

  if (titleEl) {
    titleEl.className = 'side-step-title';
    titleEl.textContent = title;
  }
  const replayBody = renderActionArtifacts(d.artifacts) + renderActionPreviewGallery(d.actionPreviews);
  if (replayEl) replayEl.innerHTML = replayBody || '<div class="side-empty">no replay artifacts.</div>';
  if (infoEl) infoEl.innerHTML = (rows.length ? rows.join('') : '<div class="side-empty">no info.</div>') + renderLlmInferenceButton(d.llmInference);
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

function setGraphDrilldown(next) {
  clearGraphDrillAnchor();
  graphDrilldown = next;
  updateGraph();
}

// ── d3 graph renderer ──────────────────────────────────
const graph = (() => {
  const svgEl = document.getElementById('graph-svg');
  const wrapEl = document.getElementById('graph-wrap');
  const emptyEl = document.getElementById('graph-empty');
  const breadcrumbEl = document.getElementById('graph-breadcrumb');
  const tooltip = document.getElementById('graph-tooltip');
  const legendEl = document.getElementById('graph-legend');
  const fitBtn = document.getElementById('graph-fit');
  const zoomInBtn = document.getElementById('graph-zoom-in');
  const zoomOutBtn = document.getElementById('graph-zoom-out');

  const svg = d3.select(svgEl);
  const root = svg.append('g').attr('class', 'graph-root');
  const linkG = root.append('g').attr('class', 'links');
  const nodeG = root.append('g').attr('class', 'nodes');
  const zoomBehavior = d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => {
      root.attr('transform', event.transform);
    });

  svg.call(zoomBehavior);

  const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(80).strength(0.7))
    .force('charge', d3.forceManyBody().strength(-260))
    .force('x', d3.forceX(d => targetX(d)).strength(0.12))
    .force('y', d3.forceY(d => targetY(d)).strength(0.05))
    .force('collide', d3.forceCollide(22))
    .on('tick', ticked);

  let nodeSel = nodeG.selectAll('g');
  let linkSel = linkG.selectAll('path');
  let nodesData = [];
  let linksData = [];
  let graphMode = 'url';

  function resize() {
    const { width, height } = wrapEl.getBoundingClientRect();
    svgEl.setAttribute('viewBox', `${-width / 2} ${-height / 2} ${width} ${height}`);
    svgEl.setAttribute('width', width);
    svgEl.setAttribute('height', height);
  }
  window.addEventListener('resize', resize);
  resize();

  function graphTransition() {
    return svg.transition().duration(220);
  }

  function zoomBy(factor) {
    graphTransition().call(zoomBehavior.scaleBy, factor);
  }

  function fitToNodes() {
    if (!nodesData.length) {
      graphTransition().call(zoomBehavior.transform, d3.zoomIdentity);
      return;
    }
    const { width, height } = wrapEl.getBoundingClientRect();
    if (!width || !height) return;
    const bounds = root.node().getBBox();
    const boundsWidth = bounds.width || 1;
    const boundsHeight = bounds.height || 1;
    const padding = 72;
    const scale = Math.max(
      0.3,
      Math.min(3, 0.92 / Math.max(boundsWidth / Math.max(1, width - padding), boundsHeight / Math.max(1, height - padding)))
    );
    const centerX = bounds.x + boundsWidth / 2;
    const centerY = bounds.y + boundsHeight / 2;
    const transform = d3.zoomIdentity
      .translate(-centerX * scale, -centerY * scale)
      .scale(scale);
    graphTransition().call(zoomBehavior.transform, transform);
  }

  if (fitBtn) fitBtn.addEventListener('click', (event) => { event.stopPropagation(); fitToNodes(); });
  if (zoomInBtn) zoomInBtn.addEventListener('click', (event) => { event.stopPropagation(); zoomBy(1.25); });
  if (zoomOutBtn) zoomOutBtn.addEventListener('click', (event) => { event.stopPropagation(); zoomBy(0.8); });

  function ticked() {
    linkSel.attr('d', linkPath);
    nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
  }

  function rootPosition(index = 0, count = 1) {
    return {
      x: graphMode === 'url' ? (index - (count - 1) / 2) * 140 : 0,
      y: graphMode === 'url' ? -180 : -220,
    };
  }

  function targetX(d) {
    if (d && d.isRoot && d._rootPin) return d._rootPin.x;
    if (d && d.isRoot) return rootPosition().x;
    return 0;
  }

  function targetY(d) {
    if (d && d.isRoot && d._rootPin) return d._rootPin.y;
    return d && d.isRoot ? rootPosition().y : 90;
  }

  function normalizeGraphNode(src) {
    return {
      isRoot: false,
      isCurrent: false,
      drillable: false,
      ...src,
    };
  }

  function drillAnchorForNode(node) {
    if (graphMode === 'url' || !graphDrillAnchor || !node) return null;
    if (graphDrillAnchor.id !== node.id) return null;
    if (!Number.isFinite(graphDrillAnchor.x) || !Number.isFinite(graphDrillAnchor.y)) return null;
    return { x: graphDrillAnchor.x, y: graphDrillAnchor.y };
  }

  function arrangeGraphNodes(nodes, previousById) {
    const rootNodes = nodes.filter(n => n.isRoot);
    const rootsById = new Map(rootNodes.map((node, index) => {
      const pinned = drillAnchorForNode(node) || rootPosition(index, rootNodes.length);
      node._rootPin = pinned;
      node.fx = pinned.x;
      node.fy = pinned.y;
      node.x = pinned.x;
      node.y = pinned.y;
      return [node.id, node];
    }));
    const parentRoot = rootNodes[0] || null;
    const childNodes = nodes.filter(n => !n.isRoot);
    childNodes.forEach((node, index) => {
      node.fx = null;
      node.fy = null;
      if (previousById.has(node.id) && Number.isFinite(node.x) && Number.isFinite(node.y)) return;
      const parent = parentRoot || rootsById.get(node.urlId);
      const baseX = parent ? parent.fx : -80;
      const baseY = parent ? parent.fy : 0;
      const offsetX = (index - (childNodes.length - 1) / 2) * 42;
      node.x = baseX + offsetX;
      node.y = baseY + 150;
    });
  }

  function linkPath(d) {
    const source = d.source || {};
    const target = d.target || {};
    const sx = source.x || 0;
    const sy = source.y || 0;
    const tx = target.x || 0;
    const ty = target.y || 0;
    if ((source.id || source) === (target.id || target)) {
      const r = 22 + Math.min(14, Math.log2((d.count || 1) + 1) * 4);
      return `M ${sx} ${sy - 8} C ${sx + r} ${sy - r * 1.6}, ${sx + r * 1.8} ${sy + r * 1.2}, ${sx + 4} ${sy + 8}`;
    }
    return `M ${sx} ${sy} L ${tx} ${ty}`;
  }

  function showTooltip(event, d) {
    const rows = [];
    const title = d.label || d.host || d.actionName || d.id;
    rows.push(`<div class="tt-row"><span>level</span><span class="v">${escHtml(d.type || '—')}</span></div>`);
    if (d.actionCount != null) rows.push(`<div class="tt-row"><span>actions</span><span class="v">${d.actionCount}</span></div>`);
    else if (d.visits != null) rows.push(`<div class="tt-row"><span>visits</span><span class="v">${d.visits}</span></div>`);
    if (d.drillable) rows.push(`<div class="tt-row"><span>double-click</span><span class="v">drill in</span></div>`);
    tooltip.innerHTML = `<div class="tt-url">${escHtml(title)}</div>` + rows.join('');
    tooltip.classList.remove('hidden');
    moveTooltip(event);
  }
  function moveTooltip(event) {
    const rect = wrapEl.getBoundingClientRect();
    const x = event.clientX - rect.left + 14;
    const y = event.clientY - rect.top + 14;
    const maxX = rect.width - tooltip.offsetWidth - 10;
    const maxY = rect.height - tooltip.offsetHeight - 10;
    tooltip.style.left = Math.max(6, Math.min(x, maxX)) + 'px';
    tooltip.style.top  = Math.max(6, Math.min(y, maxY)) + 'px';
  }
  function hideTooltip() { tooltip.classList.add('hidden'); }

  function graphNodeWorkCount(d) {
    if (!d) return 0;
    if (Number.isFinite(d.actionCount)) return d.actionCount;
    return Number.isFinite(d.visits) ? d.visits : 0;
  }

  function graphNodeFill(d, maxWorkCount) {
    const count = graphNodeWorkCount(d);
    if (!count || !maxWorkCount) return d3.interpolateViridis(0.12);
    const t = 0.12 + (Math.min(count, maxWorkCount) / maxWorkCount) * 0.82;
    return d3.interpolateViridis(t);
  }

  function updateGraphLegend(maxWorkCount, hasNodes) {
    if (!legendEl) return;
    if (!hasNodes) {
      legendEl.classList.add('hidden');
      return;
    }
    const maxLabel = legendEl.querySelector('[data-legend-max]');
    if (maxLabel) maxLabel.textContent = `max ${maxWorkCount}`;
    legendEl.classList.remove('hidden');
  }

  function drag() {
    return d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        if (d.isRoot) {
          const pinned = d._rootPin || rootPosition();
          d.fx = pinned.x;
          d.fy = pinned.y;
          return;
        }
        d.fx = null; d.fy = null;
      });
  }

  function renderBreadcrumb(payload) {
    const crumbs = (payload && payload.breadcrumb) || [];
    const parts = [];
    crumbs.forEach((crumb, idx) => {
      parts.push(`<button type="button" data-idx="${idx}">${escHtml(crumb.label)}</button>`);
      parts.push('<span class="sep">/</span>');
    });
    const current = payload.mode === 'url' ? 'URLs' : (payload.mode === 'viewport' ? 'viewports' : 'actions');
    parts.push(`<span>${escHtml(current)}</span>`);
    breadcrumbEl.innerHTML = parts.join('');
    breadcrumbEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const crumb = crumbs[Number(btn.dataset.idx || 0)];
        if (!crumb || crumb.level === 'url') {
          setGraphDrilldown({ level: 'url', urlId: null, viewportId: null });
        } else if (crumb.level === 'viewport') {
          setGraphDrilldown({ level: 'viewport', urlId: crumb.urlId, viewportId: null });
        }
      });
    });
  }

  function update(payload) {
    graphMode = payload.mode || 'url';
    emptyEl.textContent = payload.mode === 'url' ? 'no navigation yet.' : 'no child nodes yet.';
    renderBreadcrumb(payload);
    const levelEl = document.getElementById('graph-level');
    const nodeCountEl = document.getElementById('graph-node-count');
    const edgeCountEl = document.getElementById('graph-edge-count');
    if (levelEl)     levelEl.textContent = payload.mode === 'url' ? 'URLs' : (payload.mode === 'viewport' ? 'viewports' : 'actions');
    if (nodeCountEl) nodeCountEl.textContent = String((payload.nodes || []).length);
    if (edgeCountEl) edgeCountEl.textContent = String((payload.links || []).length);

    const prevById = new Map(nodesData.map(n => [n.id, n]));
    nodesData = (payload.nodes || []).map(src => {
      const prev = prevById.get(src.id);
      return Object.assign(prev || {}, normalizeGraphNode(src));
    });
    arrangeGraphNodes(nodesData, prevById);
    linksData = (payload.links || []).map(e => ({ ...e }));
    const maxWorkCount = Math.max(1, ...nodesData.map(graphNodeWorkCount));
    updateGraphLegend(maxWorkCount, nodesData.length > 0);

    emptyEl.style.display = nodesData.length ? 'none' : 'flex';

    linkSel = linkG.selectAll('path.graph-link').data(linksData, d =>
      (d.source.id || d.source) + '|' + (d.target.id || d.target)
    );
    linkSel.exit().remove();
    linkSel = linkSel.enter().append('path').attr('class', 'graph-link').merge(linkSel);
    linkSel
      .classed('cycle', d => !!d.isCycleEdge)
      .attr('stroke-width', d => d.isCycleEdge ? Math.min(4.5, 2 + Math.log2((d.count || 1) + 1)) : Math.min(3, 1 + Math.log2((d.count || 1) + 1)));

    nodeSel = nodeG.selectAll('g.graph-node').data(nodesData, d => d.id);
    nodeSel.exit().remove();
    const enter = nodeSel.enter().append('g')
      .attr('class', 'graph-node')
      .call(drag())
      .on('click', (event, d) => { event.stopPropagation(); selectGraphNode(d); })
      .on('dblclick', (event, d) => { event.stopPropagation(); drillGraphNode(d); })
      .on('mouseenter', showTooltip)
      .on('mousemove', moveTooltip)
      .on('mouseleave', hideTooltip);
    enter.append('circle').attr('r', 8);
    enter.append('text').attr('dx', 12).attr('dy', 4);
    nodeSel = enter.merge(nodeSel);
    nodeSel
      .classed('root', d => d.isRoot)
      .classed('url', d => d.type === 'url')
      .classed('viewport', d => d.type === 'viewport')
      .classed('action', d => d.type === 'action')
      .classed('drillable', d => !!d.drillable)
      .classed('current', d => !!d.isCurrent)
      .classed('running', d => isRunningGraphNode(d))
      .classed('selected', d => d.id === selectedNodeId)
      .style('--graph-node-fill', d => graphNodeFill(d, maxWorkCount));
    nodeSel.select('circle').attr('r', d => 6 + Math.min(8, Math.log2((d.visits || 1) + 1) * 2));
    nodeSel.select('text').text(d => d.label || d.id);

    simulation.nodes(nodesData);
    simulation.force('link').links(linksData);
    simulation.force('x').x(d => targetX(d));
    simulation.force('y').y(d => targetY(d));
    simulation.alpha(0.6).restart();
  }


  function reset() {
    nodesData = [];
    linksData = [];
    linkG.selectAll('*').remove();
    nodeG.selectAll('*').remove();
    hideTooltip();
    updateGraphLegend(1, false);
    breadcrumbEl.innerHTML = '<span>URLs</span>';
    emptyEl.style.display = 'flex';
    emptyEl.textContent = 'no navigation yet.';
    simulation.nodes([]);
    simulation.force('link').links([]);
  }

  function refreshSelection() {
    nodeG.selectAll('g.graph-node').classed('selected', d => d.id === selectedNodeId);
  }

  function refreshRunning() {
    nodeG.selectAll('g.graph-node').classed('running', d => isRunningGraphNode(d));
  }

  svg.on('click', () => clearGraphSelection());

  return { update, reset, resize, refreshSelection, refreshRunning };
})();

function updateGraph() { graph.update(selectedGraphData()); }
function resetGraph()  { resetTrajectoryGraphState(); clearGraphSelection(); graph.reset(); }
function resizeGraph() { graph.resize(); }

window.updateGraph = updateGraph;
window.resetGraph = resetGraph;
window.resizeGraph = resizeGraph;
window.clearGraphSelection = clearGraphSelection;
window.selectGraphActionForStep = selectGraphActionForStep;
window.recordActionExecution = recordActionExecution;
window.setGraphRunningStep = setGraphRunningStep;
window.clearGraphRunningStep = clearGraphRunningStep;
