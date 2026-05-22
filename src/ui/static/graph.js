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
  const before = escHtml(beforeHref);
  const after = escHtml(afterHref);
  return `
    <div class="artifact-compare-control">
      <div class="artifact-compare-title">Compare · <a class="artifact-link" target="_blank" rel="noreferrer" href="${before}">open before</a> · <a class="artifact-link" target="_blank" rel="noreferrer" href="${after}">open after</a></div>
      <div class="artifact-split">
        <figure><figcaption>Before</figcaption><a target="_blank" rel="noreferrer" href="${before}"><img src="${before}" alt="Before screenshot"></a></figure>
        <figure><figcaption>After</figcaption><a target="_blank" rel="noreferrer" href="${after}"><img src="${after}" alt="After screenshot"></a></figure>
      </div>
    </div>`;
}

function renderActionArtifacts(artifacts) {
  if (!artifacts) return '';
  const actionClip = replayArtifactHref(artifacts.action_clip_gif_path, 'history');
  const fallbackActionGif = replayArtifactHref(artifacts.action_gif_path, 'history');
  const beforeShot = replayArtifactHref(artifacts.before_screenshot_path, 'history');
  const afterShot = replayArtifactHref(artifacts.after_screenshot_path || artifacts.screenshot_path, 'history');
  const video = replayArtifactHref(artifacts.video_path, 'video');
  const cards = [
    renderActionReplayCard('Action replay', actionClip),
    !actionClip && fallbackActionGif ? renderArtifactCard('Before/after GIF', fallbackActionGif) : '',
    renderBeforeAfterCompare(beforeShot, afterShot),
  ].filter(Boolean);
  const videoCard = renderArtifactCard('session video', video, 'video');
  const names = [];
  if (artifacts.action_clip_gif_path) names.push(`clip=${escHtml(artifacts.action_clip_gif_path)}`);
  if (artifacts.action_gif_path) names.push(`before_after_gif=${escHtml(artifacts.action_gif_path)}`);
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

function renderLlmInferenceBody(inference) {
  if (!inference) return '';
  return `
    <div class="llm-raw-title">Raw context</div>
    <pre>${escHtml(formatRawJson(inference.rawContext))}</pre>
    <div class="llm-raw-title">Output response</div>
    <pre>${escHtml(formatRawJson(inference.rawResponse))}</pre>`;
}

function browserStateArtifactInfo(artifacts) {
  if (!artifacts) return null;
  const domHref = replayArtifactHref(artifacts.html_path || artifacts.after_html_path, 'history');
  const ariaHref = replayArtifactHref(artifacts.a11y_path || artifacts.after_a11y_path, 'history');
  const metadataHref = replayArtifactHref(artifacts.metadata_path || artifacts.after_metadata_path, 'history');
  if (!domHref && !ariaHref) return null;
  return {
    domHref,
    ariaHref,
    metadataHref,
    a11ySource: artifacts.a11y_source || '',
    a11yStatus: artifacts.a11y_capture_status || '',
    a11yError: artifacts.a11y_capture_error || '',
  };
}

function renderBrowserStatePreview(title, href, kind) {
  if (!href) return '';
  const safeHref = escHtml(href);
  return `
    <div class="llm-raw-title">${escHtml(title)} · <a class="artifact-link" target="_blank" rel="noreferrer" href="${safeHref}">open</a></div>
    <pre class="browser-state-preview" data-browser-state-src="${safeHref}" data-browser-state-kind="${escHtml(kind)}">Open this section to load ${escHtml(kind)} state…</pre>`;
}

function renderBrowserStateMetaRow(label, value) {
  return `<div class="bullet"><span class="dot">•</span><span><span class="k">${escHtml(label)}</span> <span class="v">${escHtml(value)}</span></span></div>`;
}

function renderBrowserStateMetaLink(label, href, linkText) {
  return `<div class="bullet"><span class="dot">•</span><span><span class="k">${escHtml(label)}</span> <a class="artifact-link" target="_blank" rel="noreferrer" href="${escHtml(href)}">${escHtml(linkText)}</a></span></div>`;
}

function renderBrowserStateBody(artifacts) {
  const state = browserStateArtifactInfo(artifacts);
  if (!state) return '';
  const metaRows = [];
  if (state.a11ySource) metaRows.push(renderBrowserStateMetaRow('ARIA source', state.a11ySource));
  if (state.a11yStatus) metaRows.push(renderBrowserStateMetaRow('ARIA capture', state.a11yStatus));
  if (state.a11yError) metaRows.push(renderBrowserStateMetaRow('ARIA error', state.a11yError));
  if (state.metadataHref) metaRows.push(renderBrowserStateMetaLink('State metadata', state.metadataHref, 'open JSON'));
  const previews = [
    renderBrowserStatePreview('DOM snapshot', state.domHref, 'DOM'),
    renderBrowserStatePreview('ARIA snapshot', state.ariaHref, 'ARIA'),
  ].filter(Boolean).join('');
  return `
    ${metaRows.join('')}
    ${previews || '<div class="side-empty">No DOM or ARIA artifact for this action.</div>'}`;
}

function setOptionalSideSection(section, body, content) {
  if (!section || !body) return;
  if (!content) {
    body.innerHTML = '';
    section.hidden = true;
    section.open = false;
    return;
  }
  body.innerHTML = content;
  section.hidden = false;
}

function renderRightPanelAuxiliarySections(inference, artifacts) {
  const llmSection = document.getElementById('side-llm-raw-section');
  const llmBody = document.getElementById('side-llm-raw');
  const browserStateSection = document.getElementById('side-browser-state-section');
  const browserStateBody = document.getElementById('side-browser-state');

  setOptionalSideSection(llmSection, llmBody, renderLlmInferenceBody(inference));
  const browserStateContent = renderBrowserStateBody(artifacts);
  setOptionalSideSection(browserStateSection, browserStateBody, browserStateContent);
  if (browserStateContent && browserStateSection) {
    hydrateBrowserStateButtons(browserStateSection);
    if (browserStateSection.open) loadBrowserStatePreviews(browserStateSection);
  }
}

async function loadBrowserStatePreviews(container) {
  const previews = Array.from(container.querySelectorAll('pre[data-browser-state-src]'))
    .filter(pre => pre.dataset.browserStateLoaded !== 'true');
  await Promise.all(previews.map(async (pre) => {
    const src = pre.dataset.browserStateSrc;
    const kind = pre.dataset.browserStateKind || 'browser';
    if (!src) return;
    pre.dataset.browserStateLoaded = 'true';
    pre.textContent = `Loading ${kind} state…`;
    try {
      const response = await fetch(src, { cache: 'no-store' });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`.trim());
      const text = await response.text();
      pre.textContent = text || '(empty)';
    } catch (error) {
      pre.dataset.browserStateLoaded = 'false';
      pre.textContent = `Unable to load ${kind} state: ${error?.message ?? String(error)}`;
    }
  }));
}

function hydrateBrowserStateButtons(root = document) {
  if (!root || typeof root.querySelectorAll !== 'function') return;
  const detailsNodes = [];
  if (typeof root.matches === 'function' && root.matches('details.browser-state-details')) {
    detailsNodes.push(root);
  }
  detailsNodes.push(...root.querySelectorAll('details.browser-state-details'));
  detailsNodes.forEach(details => {
    if (details.dataset.browserStateBound === 'true') return;
    details.dataset.browserStateBound = 'true';
    details.addEventListener('toggle', () => {
      if (details.open) loadBrowserStatePreviews(details);
    });
  });
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

function computeOwnCues(type, node, sequence) {
  let loop = false;
  let revisit = false;
  let deadEnd = false;
  const seq = sequence || [];
  let seen = false;
  for (let i = 0; i < seq.length; i++) {
    if (seq[i] !== node.id) continue;
    if (i > 0 && i < seq.length - 1 && seq[i + 1] === seq[i - 1] && seq[i] !== seq[i - 1]) loop = true;
    if (seen && (i === 0 || seq[i - 1] !== node.id)) revisit = true;
    seen = true;
  }
  const severity = (loop || revisit) ? 'red' : 'none';
  return { loop: loop, revisit: revisit, deadEnd: deadEnd, severity: severity };
}

function buildCueContext() {
  const viewportSequenceByUrl = new Map();
  for (const url of trajectoryNodes.values()) {
    viewportSequenceByUrl.set(url.id, url.viewportSequence || []);
  }
  const actionSequenceByViewport = new Map();
  for (const vp of trajectoryViewports.values()) {
    actionSequenceByViewport.set(vp.id, vp.actionSequence || []);
  }
  const ownCuesById = new Map();
  for (const url of trajectoryNodes.values()) {
    ownCuesById.set(url.id, computeOwnCues('url', url, urlSequence));
  }
  for (const vp of trajectoryViewports.values()) {
    ownCuesById.set(vp.id, computeOwnCues('viewport', vp, viewportSequenceByUrl.get(vp.urlId)));
  }
  for (const action of trajectoryActions.values()) {
    ownCuesById.set(action.id, computeOwnCues('action', action, actionSequenceByViewport.get(action.viewportId)));
  }
  return { ownCuesById: ownCuesById };
}

function rollupCueFor(type, scope, context) {
  let count = 0;
  let hasRed = false;
  const breakdown = { loop: 0, revisit: 0 };
  const tally = (id) => {
    const cues = context.ownCuesById.get(id);
    if (!cues) return;
    if (cues.loop) {
      count += 1;
      hasRed = true;
      breakdown.loop += 1;
    }
    if (cues.revisit) breakdown.revisit += 1;
  };
  if (type === 'url') {
    for (const vpId of scope.viewportIds || []) tally(vpId);
  } else if (type === 'viewport') {
    for (const actId of scope.actionIds || []) tally(actId);
  }
  return { rollupCount: count, rollupSeverity: hasRed ? 'red' : 'none', rollupBreakdown: breakdown };
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

function attachCueFields(type, src, sequence, context) {
  const own = computeOwnCues(type, src, sequence);
  const rollup = rollupCueFor(type, src, context);
  const rollupCount = rollup.rollupCount;
  const ownSeverity = own.severity;
  const badgeCount = rollupCount;
  return {
    ownCues: own,
    ownSeverity: ownSeverity,
    rollupCount: rollupCount,
    rollupSeverity: rollup.rollupSeverity,
    rollupBreakdown: rollup.rollupBreakdown,
    badgeCount: badgeCount,
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
  if (replayEl) replayEl.innerHTML = replayBody || '<div class="side-empty">no replay artifacts.</div>';
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

function scheduleGraphFit(delay = 320) {
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
  const GRAPH_TREE_LAYER_SPACING = 96;
  const GRAPH_TREE_SIBLING_SPACING = 118;
  const zoomBehavior = d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => {
      root.attr('transform', event.transform);
    });

  svg.call(zoomBehavior);

  const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(90).strength(1).iterations(4))
    .force('charge', d3.forceManyBody().strength(-160).distanceMax(360))
    .force('center', d3.forceCenter(0, 0).strength(0.05))
    .force('collide', d3.forceCollide(34).strength(1).iterations(2))
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
    const padding = 80;
    const scale = Math.max(
      0.3,
      Math.min(3, 0.95 / Math.max(boundsWidth / Math.max(1, width - padding), boundsHeight / Math.max(1, height - padding)))
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
    if (d && Number.isFinite(d._targetX)) return d._targetX;
    return 0;
  }

  function targetY(d) {
    if (d && d.isRoot && d._rootPin) return d._rootPin.y;
    if (d && Number.isFinite(d._targetY)) return d._targetY;
    return 90;
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
    if (graphDrillAnchor.toLevel !== graphMode) return null;
    if (!Number.isFinite(graphDrillAnchor.x) || !Number.isFinite(graphDrillAnchor.y)) return null;
    return { x: graphDrillAnchor.x, y: graphDrillAnchor.y };
  }

  function linkEndpointId(endpoint) {
    if (endpoint && typeof endpoint === 'object') return endpoint.id;
    return endpoint;
  }

  function isLinearAcyclicGraph(nodes, acyclicLinks) {
    if (linksData.some(e => e.isCycleEdge)) return false;
    if (nodes.length <= 1) return true;
    if (acyclicLinks.length !== nodes.length - 1) return false;
    const ids = new Set(nodes.map(n => n.id));
    const incoming = new Map(nodes.map(n => [n.id, 0]));
    const outgoing = new Map(nodes.map(n => [n.id, 0]));
    acyclicLinks.forEach(link => {
      const sourceId = linkEndpointId(link.source);
      const targetId = linkEndpointId(link.target);
      if (!ids.has(sourceId) || !ids.has(targetId)) return;
      outgoing.set(sourceId, (outgoing.get(sourceId) || 0) + 1);
      incoming.set(targetId, (incoming.get(targetId) || 0) + 1);
    });
    let startCount = 0;
    let endCount = 0;
    for (const node of nodes) {
      const inCount = incoming.get(node.id) || 0;
      const outCount = outgoing.get(node.id) || 0;
      if (inCount > 1 || outCount > 1) return false;
      if (inCount === 0) startCount += 1;
      if (outCount === 0) endCount += 1;
    }
    return startCount === 1 && endCount === 1;
  }

  function buildTopDownLayoutTargets(nodes) {
    const orderedNodes = [...nodes].sort((a, b) => {
      const bySequence = (a._sequenceIndex || 0) - (b._sequenceIndex || 0);
      if (bySequence) return bySequence;
      return String(a.id).localeCompare(String(b.id));
    });
    const topY = graphMode === 'url' ? -180 : -220;
    const acyclicLinks = linksData.filter(e => !e.isCycleEdge);
    if (isLinearAcyclicGraph(orderedNodes, acyclicLinks)) {
      return new Map(orderedNodes.map((node, index) => [node.id, { x: 0, y: topY + index * GRAPH_TREE_LAYER_SPACING }]));
    }

    const nodesById = new Map(orderedNodes.map(node => [node.id, node]));
    const childrenById = new Map(orderedNodes.map(node => [node.id, []]));
    const incomingCount = new Map(orderedNodes.map(node => [node.id, 0]));
    acyclicLinks.forEach(link => {
      const sourceId = linkEndpointId(link.source);
      const targetId = linkEndpointId(link.target);
      if (!nodesById.has(sourceId) || !nodesById.has(targetId) || sourceId === targetId) return;
      childrenById.get(sourceId).push(targetId);
      incomingCount.set(targetId, (incomingCount.get(targetId) || 0) + 1);
    });
    childrenById.forEach(children => {
      children.sort((a, b) => {
        const left = nodesById.get(a);
        const right = nodesById.get(b);
        return (left._sequenceIndex || 0) - (right._sequenceIndex || 0);
      });
    });

    const roots = orderedNodes.filter(node => (incomingCount.get(node.id) || 0) === 0);
    const queue = (roots.length ? roots : orderedNodes.slice(0, 1)).map(node => ({ id: node.id, depth: 0 }));
    const depthById = new Map();
    while (queue.length) {
      const current = queue.shift();
      if (depthById.has(current.id) && depthById.get(current.id) <= current.depth) continue;
      depthById.set(current.id, current.depth);
      for (const childId of childrenById.get(current.id) || []) {
        queue.push({ id: childId, depth: current.depth + 1 });
      }
    }
    orderedNodes.forEach((node, index) => {
      if (!depthById.has(node.id)) depthById.set(node.id, index);
    });

    const levels = new Map();
    orderedNodes.forEach(node => {
      const depth = depthById.get(node.id) || 0;
      if (!levels.has(depth)) levels.set(depth, []);
      levels.get(depth).push(node);
    });

    const targets = new Map();
    Array.from(levels.keys()).sort((a, b) => a - b).forEach(depth => {
      const levelNodes = levels.get(depth).sort((a, b) => {
        const bySequence = (a._sequenceIndex || 0) - (b._sequenceIndex || 0);
        if (bySequence) return bySequence;
        return String(a.id).localeCompare(String(b.id));
      });
      levelNodes.forEach((node, index) => {
        targets.set(node.id, {
          x: (index - (levelNodes.length - 1) / 2) * GRAPH_TREE_SIBLING_SPACING,
          y: topY + depth * GRAPH_TREE_LAYER_SPACING,
        });
      });
    });
    return targets;
  }

  function arrangeGraphNodes(nodes, previousById) {
    const rootNodes = nodes.filter(n => n.isRoot);
    const layoutTargets = buildTopDownLayoutTargets(nodes);
    const pinRoots = graphMode !== 'url';
    const rootsById = new Map(rootNodes.map((node, index) => {
      const pinned = drillAnchorForNode(node) || rootPosition(index, rootNodes.length);
      const target = layoutTargets.get(node.id) || pinned;
      node._targetX = target.x;
      node._targetY = target.y;
      if (pinRoots) {
        node._rootPin = pinned;
        node.fx = pinned.x;
        node.fy = pinned.y;
      } else {
        node._rootPin = null;
        node.fx = null;
        node.fy = null;
      }
      if (!previousById.has(node.id) || !Number.isFinite(node.x) || !Number.isFinite(node.y)) {
        node.x = target.x;
        node.y = target.y;
      }
      return [node.id, node];
    }));
    nodes.filter(n => !n.isRoot).forEach((node) => {
      node.fx = null;
      node.fy = null;
      const target = layoutTargets.get(node.id) || { x: 0, y: 90 };
      node._targetX = target.x;
      node._targetY = target.y;
      if (previousById.has(node.id) && Number.isFinite(node.x) && Number.isFinite(node.y)) return;
      node.x = target.x;
      node.y = target.y;
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
    const dx = tx - sx;
    const dy = ty - sy;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    const sourceR = (typeof source === 'object' && source) ? graphNodeRadius(source) : 7;
    const targetR = (typeof target === 'object' && target) ? graphNodeRadius(target) : 7;
    const x1 = sx + ux * sourceR;
    const y1 = sy + uy * sourceR;
    const x2 = tx - ux * targetR;
    const y2 = ty - uy * targetR;
    return `M ${x1} ${y1} L ${x2} ${y2}`;
  }

  function showTooltip(event, d) {
    const rows = [];
    const title = d.label || d.host || d.actionName || d.id;
    rows.push(`<div class="tt-row"><span>level</span><span class="v">${escHtml(d.type || '—')}</span></div>`);
    if (d.isStart && d.isEnd) rows.push(`<div class="tt-row"><span>flow</span><span class="v">start & end</span></div>`);
    else if (d.isStart) rows.push(`<div class="tt-row"><span>flow</span><span class="v">start ▶</span></div>`);
    else if (d.isEnd) rows.push(`<div class="tt-row"><span>flow</span><span class="v">end ■</span></div>`);
    if (d.actionStepCount != null) rows.push(`<div class="tt-row"><span>total steps</span><span class="v">${d.actionStepCount}</span></div>`);
    if (d.actionCount != null) rows.push(`<div class="tt-row"><span>unique actions</span><span class="v">${d.actionCount}</span></div>`);
    if (d.visits != null) rows.push(`<div class="tt-row"><span>visits</span><span class="v">${d.visits}</span></div>`);
    if (d.drillable) rows.push(`<div class="tt-row"><span>double-click</span><span class="v">drill in</span></div>`);
    const cueRows = [];
    if (d && d.ownCues) {
      const own = d.ownCues;
      const inside = d.rollupBreakdown || { loop: 0, revisit: 0 };
      const loopOwn = own.loop ? 1 : 0;
      const revisitOwn = own.revisit ? 1 : 0;
      if (loopOwn || inside.loop) cueRows.push(`<div class="tt-row"><span>loop</span><span class="v">${loopOwn} own / ${inside.loop} inside</span></div>`);
      if (revisitOwn || inside.revisit) cueRows.push(`<div class="tt-row"><span>revisit</span><span class="v">${revisitOwn} own / ${inside.revisit} inside</span></div>`);
    }
    const cueSection = cueRows.length
      ? `<div class="tt-section">Cues</div>` + cueRows.join('')
      : '';
    tooltip.innerHTML = `<div class="tt-url">${escHtml(title)}</div>` + rows.join('') + cueSection;
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
    if (Number.isFinite(d.actionStepCount)) return d.actionStepCount;
    if (Array.isArray(d.stepIds) && d.stepIds.length) return d.stepIds.length;
    if (Number.isFinite(d.actionCount)) return d.actionCount;
    return Number.isFinite(d.visits) ? d.visits : 0;
  }

  function trajectoryMaxWorkCount() {
    let max = 0;
    trajectoryNodes.forEach(url => {
      const count = actionStepCountForActionIds(url.actionIds);
      if (count > max) max = count;
    });
    return max;
  }

  function graphNodeRadius(d) {
    const base = 7;
    const count = graphNodeWorkCount(d);
    return base + Math.min(9, Math.log2((count || 1) + 1) * 1.8);
  }

  function levelEndpointShape(d) {
    if (!d || (!d.isStart && !d.isEnd)) return '';
    const r = graphNodeRadius(d);
    if (d.isStart && d.isEnd) {
      const s = r * 1.25;
      return `M 0 ${-s} L ${s} 0 L 0 ${s} L ${-s} 0 Z`;
    }
    if (d.isStart) {
      const w = r * 1.35;
      const h = r * 1.15;
      return `M ${-w * 0.65} ${-h} L ${w} 0 L ${-w * 0.65} ${h} Z`;
    }
    const s = r * 1.05;
    return `M ${-s} ${-s} L ${s} ${-s} L ${s} ${s} L ${-s} ${s} Z`;
  }

  function graphNodeFill(d, maxWorkCount) {
    const count = graphNodeWorkCount(d);
    if (!count || !maxWorkCount) return d3.interpolateViridis(0.12);
    const normalized = Math.sqrt(Math.min(count, maxWorkCount) / maxWorkCount);
    const t = 0.12 + normalized * 0.82;
    return d3.interpolateViridis(t);
  }

  function updateGraphLegend(maxWorkCount, hasNodes) {
    if (!legendEl) return;
    if (!hasNodes) {
      legendEl.classList.add('hidden');
      return;
    }
    const roundedMaxWorkCount = Math.round(Number(maxWorkCount) || 0);
    const maxLabel = legendEl.querySelector('[data-legend-max]');
    if (maxLabel) maxLabel.textContent = `${roundedMaxWorkCount}`;
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
          if (d._rootPin) {
            d.fx = d._rootPin.x;
            d.fy = d._rootPin.y;
          } else {
            d.fx = null;
            d.fy = null;
          }
          return;
        }
        d.fx = null; d.fy = null;
      });
  }

  function layerName(level) {
    if (level === 'action') return 'Action layer';
    if (level === 'viewport') return 'Viewport layer';
    return 'URL layer';
  }

  function renderBreadcrumb(payload) {
    const crumbs = (payload && payload.breadcrumb) || [];
    const parts = [];
    crumbs.forEach((crumb, idx) => {
      parts.push(`<button type="button" data-idx="${idx}">${escHtml(layerName(crumb.level))}</button>`);
      parts.push('<span class="sep">›</span>');
    });
    const parentLabel = payload && payload.parentLabel && payload.mode !== 'url' ? payload.parentLabel : null;
    parts.push(`<span class="current-layer">${escHtml(layerName(payload.mode))}</span>`);
    if (parentLabel) parts.push(`<span class="parent-label">inside ${escHtml(parentLabel)}</span>`);
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
    function cueBadgeClass(d) {
      if (!d || !(d.badgeCount > 0)) return { circleClass: null, textClass: null, hidden: true };
      if (d.type === 'action') return { circleClass: null, textClass: null, hidden: true };
      if (d.ownSeverity === 'red') return { circleClass: 'own-red', textClass: 'on-fill', hidden: false };
      if (d.rollupSeverity === 'red') return { circleClass: 'rollup-red', textClass: 'on-stroke', hidden: false };
      return { circleClass: null, textClass: null, hidden: true };
    }

    graphMode = payload.mode || 'url';
    emptyEl.textContent = payload.mode === 'url' ? 'no navigation yet.' : 'no child nodes yet.';
    renderBreadcrumb(payload);
    const levelEl = document.getElementById('graph-level');
    const nodeCountEl = document.getElementById('graph-node-count');
    const edgeCountEl = document.getElementById('graph-edge-count');
    if (levelEl)     levelEl.textContent = payload.mode === 'url' ? 'URLs' : (payload.mode === 'viewport' ? 'viewports' : 'actions');
    if (nodeCountEl) nodeCountEl.textContent = String((payload.nodes || []).length);
    if (edgeCountEl) edgeCountEl.textContent = String((payload.links || []).length);

    const previousNodeIds = new Set(nodesData.map(n => n.id));
    const previousLinkKeys = new Set(linksData.map(e => `${edgeEndpointId(e.source)}|${edgeEndpointId(e.target)}`));
    const incomingNodes = payload.nodes || [];
    const incomingLinks = payload.links || [];
    const structureChanged = incomingNodes.length !== nodesData.length ||
      incomingLinks.length !== linksData.length ||
      incomingNodes.some(n => !previousNodeIds.has(n.id)) ||
      incomingLinks.some(e => !previousLinkKeys.has(`${edgeEndpointId(e.source)}|${edgeEndpointId(e.target)}`));

    const prevById = new Map(nodesData.map(n => [n.id, n]));
    nodesData = incomingNodes.map(src => {
      const prev = prevById.get(src.id);
      return Object.assign(prev || {}, normalizeGraphNode(src));
    });
    linksData = incomingLinks.map(e => ({ ...e }));
    arrangeGraphNodes(nodesData, prevById);
    const maxWorkCount = Math.max(1, trajectoryMaxWorkCount(), ...nodesData.map(graphNodeWorkCount));
    updateGraphLegend(maxWorkCount, nodesData.length > 0);

    emptyEl.style.display = nodesData.length ? 'none' : 'flex';

    linkSel = linkG.selectAll('path.graph-link').data(linksData, d =>
      (d.source.id || d.source) + '|' + (d.target.id || d.target)
    );
    linkSel.exit().remove();
    linkSel = linkSel.enter().append('path').attr('class', 'graph-link').merge(linkSel);
    linkSel
      .classed('cycle', d => !!d.isCycleEdge)
      .attr('stroke-width', d => {
        const count = d.count || 1;
        const extra = 1.5 * Math.log2(count);
        return d.isCycleEdge ? Math.min(8, 2 + extra) : Math.min(6, 1 + extra);
      });

    nodeSel = nodeG.selectAll('g.graph-node').data(nodesData, d => d.id);
    nodeSel.exit().remove();
    const enter = nodeSel.enter().append('g')
      .attr('class', 'graph-node')
      .call(drag())
      .on('click', (event, d) => { event.stopPropagation(); selectGraphNode(d); })
      .on('dblclick', (event, d) => { event.stopPropagation(); hideTooltip(); drillGraphNode(d); })
      .on('mouseenter', showTooltip)
      .on('mousemove', moveTooltip)
      .on('mouseleave', hideTooltip);
    enter.append('circle').attr('r', 8);
    enter.append('path').attr('class', 'graph-node-shape');
    enter.append('text').attr('class', 'graph-node-label').attr('dx', 12).attr('dy', 4);
    const badgeEnter = enter.append('g').attr('class', 'node-cue-badge');
    badgeEnter.append('circle').attr('r', 8);
    badgeEnter.append('text');
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
      .classed('start', d => !!d.isStart)
      .classed('end', d => !!d.isEnd)
      .style('--graph-node-fill', d => graphNodeFill(d, maxWorkCount));
    nodeSel.select('circle').attr('r', d => graphNodeRadius(d));
    nodeSel.select('path.graph-node-shape')
      .attr('d', d => levelEndpointShape(d))
      .style('display', d => (d.isStart || d.isEnd) ? null : 'none');
    nodeSel.select('text.graph-node-label').text(displayGraphNodeLabel);
    const badgeSel = nodeSel.select('g.node-cue-badge');
    badgeSel.each(function(d) {
      const sel = d3.select(this);
      const meta = cueBadgeClass(d);
      if (meta.hidden) {
        sel.style('display', 'none');
        return;
      }
      sel.style('display', null);
      const r = graphNodeRadius(d);
      sel.attr('transform', `translate(${r + 4},${-(r + 4)})`);
      sel.select('circle')
        .attr('class', meta.circleClass)
        .attr('r', d.badgeCount >= 10 ? 10 : 8);
      sel.select('text')
        .attr('class', meta.textClass)
        .text(String(d.badgeCount));
    });

    simulation.nodes(nodesData);
    simulation.force('link').links(linksData);
    if (structureChanged) {
      simulation.alpha(Math.max(simulation.alpha(), 0.28)).restart();
    } else {
      simulation.alpha(Math.max(simulation.alpha(), 0.06)).restart();
    }
  }


  function reset() {
    nodesData = [];
    linksData = [];
    graphRenderDirty = false;
    linkG.selectAll('*').remove();
    nodeG.selectAll('*').remove();
    hideTooltip();
    updateGraphLegend(1, false);
    breadcrumbEl.innerHTML = '<span>URL layer</span>';
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

  return { update, reset, resize, refreshSelection, refreshRunning, fitToNodes };
})();

function isGraphViewActive() {
  return document.body.classList.contains('view-graph');
}

function updateGraph({ force = false } = {}) {
  if (!force && !isGraphViewActive()) {
    graphRenderDirty = true;
    return;
  }
  graphRenderDirty = false;
  graph.update(selectedGraphData());
}

function scheduleGraphUpdate() {
  updateGraph();
}

function resetGraph()  { resetTrajectoryGraphState(); clearGraphSelection(); graphRenderDirty = false; graph.reset(); }
function resizeGraph() { graph.resize(); }

window.updateGraph = updateGraph;
window.resetGraph = resetGraph;
window.resizeGraph = resizeGraph;
window.clearGraphSelection = clearGraphSelection;
window.selectGraphActionForStep = selectGraphActionForStep;
window.recordActionExecution = recordActionExecution;
window.setGraphRunningStep = setGraphRunningStep;
window.clearGraphRunningStep = clearGraphRunningStep;
