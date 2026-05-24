const NOOP_EVIDENCE_DIFF_THRESHOLD = 0.01;

function loadArtifactImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`failed to load ${src}`));
    img.src = src;
  });
}

function normalizeNoopEvidenceText(text) {
  return String(text || '')
    .replace(/\[ref=[^\]]*\]/g, '')
    .replace(/\b\d{4,}\b/g, '#')
    .replace(/\s+/g, ' ')
    .trim();
}

function setDiffRatio(aText, bText) {
  const a = normalizeNoopEvidenceText(aText);
  const b = normalizeNoopEvidenceText(bText);
  if (!a && !b) return 0;
  if (!a || !b) return 1;
  if (a === b) return 0;
  const tokenize = (text) => text.split(/[\s<>="']+/).map(t => t.trim()).filter(Boolean);
  const aSet = new Set(tokenize(a));
  const bSet = new Set(tokenize(b));
  const union = new Set([...aSet, ...bSet]);
  if (!union.size) return 0;
  let changed = 0;
  union.forEach(token => {
    if (!aSet.has(token) || !bSet.has(token)) changed += 1;
  });
  return changed / union.size;
}

function screenshotDiffRatio(beforeSrc, afterSrc) {
  return Promise.all([loadArtifactImage(beforeSrc), loadArtifactImage(afterSrc)])
    .then(([beforeImg, afterImg]) => {
      if ((beforeImg.naturalWidth !== afterImg.naturalWidth) || (beforeImg.naturalHeight !== afterImg.naturalHeight)) {
        return 1;
      }
      const rawW = beforeImg.naturalWidth || beforeImg.width;
      const rawH = beforeImg.naturalHeight || beforeImg.height;
      if (!rawW || !rawH) return 1;
      const maxSide = 320;
      const scale = Math.min(1, maxSide / Math.max(rawW, rawH));
      const w = Math.max(1, Math.round(rawW * scale));
      const h = Math.max(1, Math.round(rawH * scale));
      const beforeCanvas = document.createElement('canvas');
      const afterCanvas = document.createElement('canvas');
      beforeCanvas.width = afterCanvas.width = w;
      beforeCanvas.height = afterCanvas.height = h;
      const beforeCtx = beforeCanvas.getContext('2d', { willReadFrequently: true });
      const afterCtx = afterCanvas.getContext('2d', { willReadFrequently: true });
      beforeCtx.drawImage(beforeImg, 0, 0, w, h);
      afterCtx.drawImage(afterImg, 0, 0, w, h);
      const beforeData = beforeCtx.getImageData(0, 0, w, h);
      const afterData = afterCtx.getImageData(0, 0, w, h);
      let changedPixels = 0;
      const threshold = 32;
      for (let i = 0; i < afterData.data.length; i += 4) {
        const dr = Math.abs(beforeData.data[i] - afterData.data[i]);
        const dg = Math.abs(beforeData.data[i + 1] - afterData.data[i + 1]);
        const db = Math.abs(beforeData.data[i + 2] - afterData.data[i + 2]);
        if ((dr + dg + db) > threshold) changedPixels += 1;
      }
      return changedPixels / (w * h);
    });
}

function artifactHrefFromName(name) {
  return replayArtifactHref(name, 'history');
}

function fetchArtifactTextByName(name) {
  const href = artifactHrefFromName(name);
  if (!href) return Promise.resolve('');
  return fetch(href, { cache: 'no-store' }).then(res => res.ok ? res.text() : '');
}

function fetchArtifactJsonByName(name) {
  const href = artifactHrefFromName(name);
  if (!href) return Promise.resolve(null);
  return fetch(href, { cache: 'no-store' }).then(res => res.ok ? res.json() : null).catch(() => null);
}

function resolveNoopEvidencePaths(artifacts) {
  const beforeMetaName = artifacts.before_metadata_path;
  const afterMetaName = artifacts.after_metadata_path || artifacts.metadata_path;
  return Promise.all([
    fetchArtifactJsonByName(beforeMetaName),
    fetchArtifactJsonByName(afterMetaName),
  ]).then(([beforeMeta, afterMeta]) => ({
    beforeHtml: (beforeMeta && beforeMeta.html_path) || artifacts.before_html_path || '',
    afterHtml: artifacts.html_path || artifacts.after_html_path || (afterMeta && afterMeta.html_path) || '',
    beforeAria: (beforeMeta && beforeMeta.a11y_path) || artifacts.before_a11y_path || '',
    afterAria: artifacts.a11y_path || artifacts.after_a11y_path || (afterMeta && afterMeta.a11y_path) || '',
    beforeScreenshot: artifacts.before_screenshot_path || (beforeMeta && beforeMeta.screenshot_path) || '',
    afterScreenshot: artifacts.after_screenshot_path || artifacts.screenshot_path || (afterMeta && afterMeta.screenshot_path) || '',
  }));
}

function evaluateNoopEvidence(artifacts) {
  return resolveNoopEvidencePaths(artifacts).then(paths => {
    if (!paths.beforeHtml || !paths.afterHtml || !paths.beforeAria || !paths.afterAria || !paths.beforeScreenshot || !paths.afterScreenshot) {
      return null;
    }
    return Promise.all([
      fetchArtifactTextByName(paths.beforeHtml),
      fetchArtifactTextByName(paths.afterHtml),
      fetchArtifactTextByName(paths.beforeAria),
      fetchArtifactTextByName(paths.afterAria),
      screenshotDiffRatio(artifactHrefFromName(paths.beforeScreenshot), artifactHrefFromName(paths.afterScreenshot)),
    ]);
  }).then(result => {
    if (!result) return null;
    const [beforeDom, afterDom, beforeAria, afterAria, screenshotRatio] = result;
    const domRatio = setDiffRatio(beforeDom, afterDom);
    const ariaRatio = setDiffRatio(beforeAria, afterAria);
    const ok = domRatio === 0 &&
      ariaRatio === 0 &&
      screenshotRatio <= NOOP_EVIDENCE_DIFF_THRESHOLD;
    return { ok, domRatio, ariaRatio, screenshotRatio };
  });
}

function formatNoopEvidenceText(evidence) {
  const pct = (value) => `${(value * 100).toFixed(2)}%`;
  return `No-op: DOM and ARIA unchanged, screenshot diff ≤ ${(NOOP_EVIDENCE_DIFF_THRESHOLD * 100).toFixed(0)}% (DOM ${pct(evidence.domRatio)}, ARIA ${pct(evidence.ariaRatio)}, screenshot ${pct(evidence.screenshotRatio)}).`;
}

function primeNoopEvidenceForAction(actionNode) {
  if (!actionNode || !actionNode.artifacts) return;
  const evidenceKey = [
    actionNode.artifacts.before_metadata_path,
    actionNode.artifacts.after_metadata_path || actionNode.artifacts.metadata_path,
    actionNode.artifacts.before_screenshot_path,
    actionNode.artifacts.after_screenshot_path || actionNode.artifacts.screenshot_path,
  ].join('|');
  if (actionNode.noopEvidenceKey === evidenceKey &&
    (actionNode.noopEvidenceStatus === 'pending' || actionNode.noopEvidenceStatus === 'pass' || actionNode.noopEvidenceStatus === 'fail')) {
    return;
  }
  actionNode.noopEvidenceKey = evidenceKey;
  actionNode.noopEvidenceStatus = 'pending';
  evaluateNoopEvidence(actionNode.artifacts).then(evidence => {
    if (actionNode.noopEvidenceKey !== evidenceKey) return;
    if (!evidence) {
      actionNode.noopEvidenceStatus = 'fail';
      actionNode.noopEvidence = null;
      scheduleGraphUpdate();
      return;
    }
    actionNode.noopEvidence = evidence;
    actionNode.noopEvidenceStatus = evidence.ok ? 'pass' : 'fail';
    actionNode.noopCount = evidence.ok ? Math.max(1, actionNode.noopCount || 0) : 0;
    scheduleGraphUpdate();
  }).catch(() => {
    if (actionNode.noopEvidenceKey !== evidenceKey) return;
    actionNode.noopEvidenceStatus = 'fail';
    actionNode.noopEvidence = null;
  });
}

function hydrateNoopEvidence(root = document) {
  const scope = root && root.querySelectorAll ? root : document;
  scope.querySelectorAll('.artifact-noop-alert[data-noop-evidence]:not([data-noop-ready])').forEach(alert => {
    alert.dataset.noopReady = 'true';
    let artifacts = null;
    try {
      artifacts = JSON.parse(alert.getAttribute('data-artifacts') || '{}');
    } catch (_) {
      alert.remove();
      return;
    }
    evaluateNoopEvidence(artifacts).then(evidence => {
      if (!evidence || !evidence.ok) {
        alert.remove();
        return;
      }
      const text = alert.querySelector('.artifact-noop-text');
      if (text) {
        text.textContent = formatNoopEvidenceText(evidence);
      }
      alert.hidden = false;
    }).catch(() => {
      alert.remove();
    });
  });
}
