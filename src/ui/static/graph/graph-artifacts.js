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
  // P5: slider overlay. The "after" image stacks on top and a CSS clip-path
  // tied to a range input reveals the "before" underneath as the user drags.
  const before = escHtml(beforeHref);
  const after = escHtml(afterHref);
  return `
    <div class="artifact-compare-control">
      <div class="artifact-compare-title">Compare · <a class="artifact-link" target="_blank" rel="noreferrer" href="${before}">open before</a> · <a class="artifact-link" target="_blank" rel="noreferrer" href="${after}">open after</a></div>
      <div class="artifact-slider" style="--split:50%">
        <img class="artifact-slider-before" src="${before}" alt="Before screenshot">
        <img class="artifact-slider-after" src="${after}" alt="After screenshot">
        <input class="artifact-slider-range" type="range" min="0" max="100" value="50" aria-label="Before/after slider"
          oninput="this.parentElement.style.setProperty('--split', this.value + '%')">
      </div>
    </div>`;
}
