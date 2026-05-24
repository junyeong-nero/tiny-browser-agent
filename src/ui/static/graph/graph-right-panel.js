// Set-based ARIA diff per outline §S3 — no LCS, no library. Lines unique to
// the pre-state are removals; lines unique to the post-state are additions;
// shared lines are context. Capped output keeps the panel snappy.
function ariaDiffLines(preText, postText, maxLines = 200) {
  const splitLines = (text) => String(text || '').split('\n').map(line => line.trim()).filter(Boolean);
  const preLines = splitLines(preText);
  const postLines = splitLines(postText);
  const preSet = new Set(preLines);
  const postSet = new Set(postLines);
  const out = [];
  let truncated = false;
  for (const line of preLines) {
    if (!postSet.has(line)) {
      if (out.length >= maxLines) { truncated = true; break; }
      out.push({ kind: 'removed', text: line });
    }
  }
  if (!truncated) {
    for (const line of postLines) {
      if (!preSet.has(line)) {
        if (out.length >= maxLines) { truncated = true; break; }
        out.push({ kind: 'added', text: line });
      }
    }
  }
  return { lines: out, truncated, preCount: preLines.length, postCount: postLines.length };
}

function renderAriaPrePostDiff(preText, postText) {
  if (!preText && !postText) return '';
  const diff = ariaDiffLines(preText, postText);
  if (!diff.lines.length) {
    return `
      <div class="llm-raw-title">ARIA diff</div>
      <div class="aria-diff aria-diff-empty">No structural change between pre and post ARIA snapshots (${diff.preCount} → ${diff.postCount} lines).</div>`;
  }
  const rows = diff.lines.map(line => {
    const prefix = line.kind === 'added' ? '+' : '−';
    return `<div class="aria-diff-line ${line.kind}"><span class="aria-diff-prefix">${prefix}</span><span class="aria-diff-text">${escHtml(line.text)}</span></div>`;
  });
  const note = diff.truncated ? '<div class="aria-diff-truncated">…diff truncated.</div>' : '';
  return `
    <div class="llm-raw-title">ARIA diff (pre → post)</div>
    <div class="aria-diff">${rows.join('')}${note}</div>`;
}

function renderActionArtifacts(artifacts) {
  if (!artifacts) return '';
  const actionClip = replayArtifactHref(artifacts.action_clip_gif_path, 'history');
  const fallbackActionGif = replayArtifactHref(artifacts.action_gif_path, 'history');
  const beforeShot = replayArtifactHref(artifacts.before_screenshot_path, 'history');
  const afterShot = replayArtifactHref(artifacts.after_screenshot_path || artifacts.screenshot_path, 'history');
  const video = replayArtifactHref(artifacts.video_path, 'video');
  // Outline §F2.4 no-op outcome cue: when the agent's action produced no
  // meaningful state change, surface a banner only after asynchronous evidence
  // checks prove DOM diff, ARIA diff, and screenshot pixel diff are all <= K.
  // The hidden placeholder is removed unless all evidence gates pass.
  const noopPayload = escHtml(JSON.stringify({
    before_metadata_path: artifacts.before_metadata_path,
    after_metadata_path: artifacts.after_metadata_path || artifacts.metadata_path,
    metadata_path: artifacts.metadata_path,
    before_html_path: artifacts.before_html_path,
    html_path: artifacts.html_path || artifacts.after_html_path,
    before_a11y_path: artifacts.before_a11y_path,
    a11y_path: artifacts.a11y_path || artifacts.after_a11y_path,
    before_screenshot_path: artifacts.before_screenshot_path,
    after_screenshot_path: artifacts.after_screenshot_path || artifacts.screenshot_path,
    screenshot_path: artifacts.screenshot_path,
  }));
  const noopAlert = (beforeShot && afterShot)
    ? `<div class="artifact-noop-alert" role="status" hidden data-noop-evidence="true" data-artifacts="${noopPayload}">
         <span class="material-symbols-rounded" aria-hidden="true">block</span>
         <span class="artifact-noop-text">Checking no-op evidence…</span>
       </div>`
    : '';
  const cards = [
    renderActionReplayCard('Action replay', actionClip),
    !actionClip && fallbackActionGif ? renderArtifactCard('Before/after GIF', fallbackActionGif) : '',
    noopAlert,
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

function renderBrowserStateBody(artifacts, actionNode) {
  const ariaDiffBlock = actionNode
    ? renderAriaPrePostDiff(actionNode.preAriaText, actionNode.postAriaText)
    : '';
  const state = browserStateArtifactInfo(artifacts);
  if (!state) return ariaDiffBlock;
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
    ${ariaDiffBlock}
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

function renderRightPanelAuxiliarySections(inference, artifacts, actionNode) {
  const llmSection = document.getElementById('side-llm-raw-section');
  const llmBody = document.getElementById('side-llm-raw');
  const browserStateSection = document.getElementById('side-browser-state-section');
  const browserStateBody = document.getElementById('side-browser-state');

  setOptionalSideSection(llmSection, llmBody, renderLlmInferenceBody(inference));
  const browserStateContent = renderBrowserStateBody(artifacts, actionNode);
  setOptionalSideSection(browserStateSection, browserStateBody, browserStateContent);
  if (browserStateContent && browserStateSection) {
    hydrateBrowserStateButtons(browserStateSection);
    if (browserStateSection.open) loadBrowserStatePreviews(browserStateSection);
  }
}

// Look up action node by step id for callers that only have stepIds (per-step
// selection path). Returns null when no graph action has been recorded yet
// (e.g. the timeline event arrives before the graph builds).
function actionNodeForStep(stepId) {
  if (stepId == null) return null;
  const actionId = actionNodeIdByStep.get(String(stepId));
  return actionId ? trajectoryActions.get(actionId) : null;
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
