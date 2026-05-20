// Simple UI intentionally has no graph view. The full panel.js still emits
// graph lifecycle calls while rendering the shared timeline, so this file keeps
// graph hooks as no-ops while preserving shared replay/artifact helpers.
function setGraphRunningStep(_stepId) {}
function clearGraphRunningStep(_stepId) {}
function resetGraph() {}
function resizeGraph() {}
function updateGraph(_payload) {}
function recordActionExecution(_event) {}
function selectGraphActionForStep(_stepId) {}
function clearGraphSelection() {}

function artifactPathName(path, expectedDir = 'history') {
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

function renderActionScreenshotCard(label, href) {
  if (!href) return '';
  const safeLabel = escHtml(label || 'Screenshot');
  const safeHref = escHtml(href);
  return `<a class="simple-screenshot-link" target="_blank" rel="noreferrer" href="${safeHref}"><img src="${safeHref}" alt="${safeLabel}"></a>`;
}

function renderBeforeAfterCompare(beforeHref, afterHref) {
  const before = beforeHref ? renderArtifactCard('Before', beforeHref) : '';
  const after = afterHref ? renderArtifactCard('After', afterHref) : '';
  if (!before && !after) return '';
  return `<div class="artifact-split">${before}${after}</div>`;
}

function renderActionArtifacts(artifacts) {
  if (!artifacts) return '';
  const afterShot = replayArtifactHref(artifacts.after_screenshot_path || artifacts.screenshot_path, 'history');
  const fallbackShot = replayArtifactHref(artifacts.before_screenshot_path, 'history');
  return renderActionScreenshotCard('Screenshot', afterShot || fallbackShot);
}

function renderRightPanelAuxiliarySections(_inference, _artifacts) {}
