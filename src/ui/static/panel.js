const dot         = document.getElementById('dot');
const statusLabel = document.getElementById('status-label');
const timeline    = document.getElementById('timeline');
const emptyState  = document.getElementById('empty-state');
const input       = document.getElementById('input');
const btn         = document.getElementById('btn');
const btnIconPath = document.getElementById('btn-icon-path');
const statusLoading = document.getElementById('status-loading');
const inputShell  = document.getElementById('input-shell');
const agentModel  = document.getElementById('agent-model');
const sessionsBtn = document.getElementById('sessions-btn');
const sessionsPanel = document.getElementById('sessions-panel');
const sessionsClose = document.getElementById('sessions-close');
const sessionsList = document.getElementById('sessions-list');
const replayBadge = document.getElementById('replay-badge');
const liveBtn = document.getElementById('live-btn');
const themeToggle = document.getElementById('theme-toggle');
const themeTogglePath = document.getElementById('theme-toggle-path');
const replayControls = document.getElementById('replay-controls');
const replayPrev = document.getElementById('replay-prev');
const replayPlay = document.getElementById('replay-play');
const replayNext = document.getElementById('replay-next');
const replaySpeed = document.getElementById('replay-speed');
const replaySlider = document.getElementById('replay-slider');
const replayProgress = document.getElementById('replay-progress');

const sideTask       = document.getElementById('side-task');
const sidePlan       = document.getElementById('side-plan');
const sideActivity   = document.getElementById('side-activity');
const metaStep       = document.getElementById('meta-step');
const metaUrl        = document.getElementById('meta-url');
const metaState      = document.getElementById('meta-state');

let isRunning = false;
let isSubmitting = false;
let isStopping = false;
let inputAllowed = false;
let reconnectDelay = 1000;
let ws = null;
let replayMode = false;
let replayPaused = true;
let replayEvents = [];
let replayIndex = 0;
let replayTimer = null;
let replaySessionId = null;
let liveSessionId = null;

let subgoals = [];
let pendingReplanFailedSubgoalId = null;
// activity[step_id] = { step, subgoalId, phaseId, what, why, outcome }
let activity = [];
let llmInferencesByStep = new Map();
const MAX_ACTIVITY = 80;
const THEME_STORAGE_KEY = "bragent.theme";
const THEME_ICON_PATHS = {
  light: 'M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.8 1.42-1.42zM1 13h3v-2H1v2zm10-12h2v3h-2V1zm9.04 2.46-1.41-1.41-1.8 1.79 1.42 1.42 1.79-1.8zM17.24 19.16l1.8 1.79 1.41-1.41-1.79-1.8-1.42 1.42zM20 11v2h3v-2h-3zm-8 9h2v3h-2v-3zM4.96 20.95l1.8-1.79-1.42-1.42-1.79 1.8 1.41 1.41zM12 6a6 6 0 1 0 0 12A6 6 0 0 0 12 6z',
  dark: 'M12 4.5A7.5 7.5 0 1 0 19.5 12 5.8 5.8 0 0 1 12 4.5z',
};

let currentTimelineStepId = null;
let currentTimelineStepGroup = null;
let selectedTimelineStepId = null;

// ── Theme ──────────────────────────────────────────────
function storedThemePreference() {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch (_) {
    return null;
  }
}

function systemThemePreference() {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? 'dark' : 'light';
  } catch (_) {
    return 'light';
  }
}

function updateThemeToggle(theme) {
  const isDark = theme === 'dark';
  const nextTheme = isDark ? 'light' : 'dark';
  const label = `Switch to ${nextTheme} theme`;
  themeToggle.setAttribute('aria-label', label);
  themeToggle.setAttribute('aria-pressed', String(isDark));
  themeToggle.setAttribute('title', label);
  themeTogglePath.setAttribute('d', THEME_ICON_PATHS[theme]);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  updateThemeToggle(theme);
}

function setupTheme() {
  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const saved = storedThemePreference();
  applyTheme(saved || systemThemePreference());

  themeToggle.addEventListener('click', () => {
    const current = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(THEME_STORAGE_KEY, next); } catch (_) {}
    applyTheme(next);
  });

  if (media) {
    const syncSystemTheme = (event) => {
      if (!storedThemePreference()) applyTheme(event.matches ? 'dark' : 'light');
    };
    if (media.addEventListener) {
      media.addEventListener('change', syncSystemTheme);
    } else if (media.addListener) {
      media.addListener(syncSystemTheme);
    }
  }
}

// ── WebSocket ──────────────────────────────────────────
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => {
    reconnectDelay = 1000;
    if (replayMode) {
      setReplayUi(true);
    } else {
      setStatus('connected', 'ready');
      if (!isRunning) setInputEnabled(true);
    }
  };
  ws.onmessage = (e) => {
    if (replayMode) return;
    try { handleEvent(JSON.parse(e.data)); } catch (_) {}
  };
  ws.onclose = () => {
    if (!replayMode) {
      setStatus('disconnected', 'disconnected');
      setInputEnabled(false);
    }
    setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 10000);
      connect();
    }, reconnectDelay);
  };
}

function setStatus(state, label) {
  dot.className = `status-dot ${state}`;
  statusLoading.classList.toggle('active', state === 'running');
  statusLabel.textContent = label;
  metaState.textContent = label;
}

function updateControlStates() {
  const stopMode = (isRunning || isSubmitting) && !replayMode;
  const canRun = inputAllowed && !stopMode;
  btn.disabled = stopMode ? isStopping : !canRun;
  btn.classList.toggle('stop', stopMode);
  btn.setAttribute('aria-label', stopMode ? 'Stop task' : 'Run task');
  btn.setAttribute('title', stopMode ? 'Stop task' : 'Run task');
  btnIconPath.setAttribute('d', stopMode ? 'M6 6h12v12H6z' : 'M8 5v14l11-7z');
}

function setInputEnabled(enabled) {
  inputAllowed = enabled;
  input.disabled = !enabled;
  inputShell.classList.toggle('disabled', !enabled);
  updateControlStates();
}

function resetTimeline() {
  timeline.replaceChildren();
  currentTimelineStepId = null;
  currentTimelineStepGroup = null;
  selectedTimelineStepId = null;
}

function setAgentModel(modelName) {
  if (modelName) agentModel.textContent = modelName;
}

// ── Timeline helpers ───────────────────────────────────
function clearEmpty() {
  if (emptyState && emptyState.parentNode) emptyState.remove();
}

function appendTimelineElement(el) {
  if (currentTimelineStepGroup) currentTimelineStepGroup.appendChild(el);
  else timeline.appendChild(el);
  timeline.scrollTop = timeline.scrollHeight;
}

function beginActionStepGroup(stepId) {
  currentTimelineStepId = stepId;
  setGraphRunningStep(stepId);
  currentTimelineStepGroup = document.createElement('div');
  currentTimelineStepGroup.className = 'action-step-group';
  currentTimelineStepGroup.dataset.stepId = String(stepId);
  timeline.appendChild(currentTimelineStepGroup);
  timeline.scrollTop = timeline.scrollHeight;
  updateTimelineHighlight();
}

function finishActionStepGroup(stepId) {
  if (currentTimelineStepId != null && String(currentTimelineStepId) === String(stepId)) {
    currentTimelineStepId = null;
    currentTimelineStepGroup = null;
  }
  clearGraphRunningStep(stepId);
}

function highlightedTimelineGroup() {
  if (selectedTimelineStepId == null) return null;
  return timeline.querySelector(`.action-step-group[data-step-id="${CSS.escape(String(selectedTimelineStepId))}"]`);
}

function scrollHighlightedTimelineStep() {
  const group = highlightedTimelineGroup();
  if (!group || !document.body.classList.contains('view-timeline')) return;
  group.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function updateTimelineHighlight() {
  timeline.querySelectorAll('.action-step-group.timeline-highlight').forEach(el => {
    el.classList.remove('timeline-highlight');
  });
  const group = highlightedTimelineGroup();
  if (!group) return;
  group.classList.add('timeline-highlight');
}

function highlightTimelineActionStep(stepId) {
  selectedTimelineStepId = stepId != null ? String(stepId) : null;
  updateTimelineHighlight();
  scrollHighlightedTimelineStep();
}

function addRow(cls, html) {
  clearEmpty();
  const el = document.createElement('div');
  el.className = `row ${cls || ''}`;
  el.innerHTML = html;
  appendTimelineElement(el);
  return el;
}

function addSpeaker(name, model) {
  clearEmpty();
  const el = document.createElement('div');
  el.className = 'speaker';
  el.innerHTML =
    `<span class="marker"></span>` +
    `<span class="name">${escHtml(name)}</span>` +
    (model ? `<span class="sep">·</span><span class="model">${escHtml(model)}</span>` : '');
  appendTimelineElement(el);
}

function addBlock(cls, html) {
  clearEmpty();
  const el = document.createElement('div');
  el.className = `block ${cls || ''}`;
  el.innerHTML = html;
  appendTimelineElement(el);
  return el;
}

// ── Sidebar helpers ────────────────────────────────────
function resetSidebar() {
  subgoals = [];
  pendingReplanFailedSubgoalId = null;
  activity = [];
  llmInferencesByStep = new Map();
  currentTimelineStepId = null;
  currentTimelineStepGroup = null;
  highlightTimelineActionStep(null);
  sideTask.className = 'side-empty';
  sideTask.textContent = 'no active task.';
  renderPlan();
  renderActivity();
  resetGraph();
  metaStep.textContent = '—';
  metaUrl.textContent  = '—';
}

function storeLlmInference(ev) {
  if (!ev || ev.step_id == null) return;
  llmInferencesByStep.set(String(ev.step_id), {
    stepId: ev.step_id,
    rawContext: ev.raw_context || null,
    rawResponse: ev.raw_response || null,
  });
}

function getLlmInferenceForStep(stepId) {
  if (stepId == null) return null;
  return llmInferencesByStep.get(String(stepId)) || null;
}

window.getLlmInferenceForStep = getLlmInferenceForStep;

function setSideTask(query) {
  sideTask.className = '';
  sideTask.textContent = query;
}

function setSubgoals(list) {
  subgoals = (list || []).map(sg => ({
    id: sg.id,
    description: sg.description,
    status: 'pending',
  }));
  renderPlan();
}

function replaceSubgoalsAfterFailed(failedId, revisedList) {
  const failedIdx = subgoals.findIndex(s => String(s.id) === String(failedId));
  if (failedIdx === -1) {
    setSubgoals(revisedList);
    renderActivity();
    return;
  }
  const revisedSubgoals = (revisedList || []).map(sg => ({
    id: sg.id,
    description: sg.description,
    status: 'pending',
  }));
  subgoals = subgoals.slice(0, failedIdx + 1).concat(revisedSubgoals);
  renderPlan();
  renderActivity();
}

function updateSubgoalStatus(id, status) {
  const sg = subgoals.find(s => String(s.id) === String(id));
  if (sg) { sg.status = status; renderPlan(); }
}

function renderPlan() {
  if (!subgoals.length) {
    sidePlan.innerHTML = '<div class="side-empty">no plan yet.</div>';
    return;
  }
  const statusIcons = {
    pending: '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm0 2a6 6 0 1 1 0 12 6 6 0 0 1 0-12z"></path></svg>',
    active: '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M8 5v14l11-7z"></path></svg>',
    done: '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.2 13.6-3.4-3.4 1.4-1.4 2 2 4.6-4.6 1.4 1.4-6 6z"></path></svg>',
    failed: '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm3.5 12.1-1.4 1.4L12 13.4l-2.1 2.1-1.4-1.4 2.1-2.1-2.1-2.1 1.4-1.4 2.1 2.1 2.1-2.1 1.4 1.4-2.1 2.1 2.1 2.1z"></path></svg>',
  };
  sidePlan.innerHTML = subgoals.map(sg => `
    <div class="todo ${sg.status}">
      <span class="status-icon">${statusIcons[sg.status] || statusIcons.pending}</span>
      <span class="text">${escHtml(sg.description)}</span>
    </div>
  `).join('');
}

function addActivity(item) {
  // item: {step, subgoalId, phaseId, what, why, outcome}
  // If a step already recorded, update in place (step can emit multiple review_metadata).
  const existingIdx = activity.findIndex(a => a.step === item.step);
  if (existingIdx !== -1) {
    activity[existingIdx] = { ...activity[existingIdx], ...item };
  } else {
    activity.push(item);
    if (activity.length > MAX_ACTIVITY) activity = activity.slice(-MAX_ACTIVITY);
  }
  renderActivity();
}

function renderActivity() {
  if (!activity.length) {
    sideActivity.innerHTML = '<div class="side-empty">no activity yet.</div>';
    return;
  }

  // Group activity by subgoalId, preserving plan order; unknowns go to an "unassigned" bucket.
  const buckets = new Map();
  const unassigned = [];
  for (const it of activity) {
    const key = it.subgoalId != null ? String(it.subgoalId) : null;
    if (key === null) { unassigned.push(it); continue; }
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(it);
  }

  const renderItem = (a) => {
    const cls = a.phaseId ? `phase-${escHtml(String(a.phaseId).replace(/^phase-/, ''))}` : '';
    const what    = a.what    ? `<div class="what">${escHtml(a.what)}</div>`       : '';
    const why     = a.why     ? `<div class="why">${escHtml(a.why)}</div>`         : '';
    const outcome = (a.outcome && a.outcome !== '—')
      ? `<div class="outcome">${escHtml(a.outcome)}</div>` : '';
    return `<div class="act-item ${cls}">
      <span class="step-no">#${escHtml(a.step)}</span>
      <span>${what}${why}${outcome}</span>
    </div>`;
  };

  const parts = [];
  // Plan-ordered subgoal groups first
  subgoals.forEach((sg, i) => {
    const key = String(sg.id);
    const items = buckets.get(key);
    if (!items || !items.length) return;
    parts.push(
      `<div class="act-group">` +
        `<div class="act-group-title">` +
          `<span class="sg-num">${String(i + 1).padStart(2,'0')}</span>` +
          `<span class="sg-desc">${escHtml(sg.description)}</span>` +
        `</div>` +
        items.map(renderItem).join('') +
      `</div>`
    );
    buckets.delete(key);
  });
  // Any remaining buckets whose subgoal id is unknown to the plan
  for (const [key, items] of buckets.entries()) {
    parts.push(
      `<div class="act-group">` +
        `<div class="act-group-title"><span class="sg-num">sg ${escHtml(key)}</span></div>` +
        items.map(renderItem).join('') +
      `</div>`
    );
  }
  if (unassigned.length) {
    parts.push(
      `<div class="act-group">` +
        `<div class="act-group-title unassigned">unassigned</div>` +
        unassigned.map(renderItem).join('') +
      `</div>`
    );
  }
  sideActivity.innerHTML = parts.join('');
}

// Tab switching (Timeline ↔ Graph)
function setMainView(view) {
  document.body.classList.toggle('view-timeline', view === 'timeline');
  document.body.classList.toggle('view-graph', view === 'graph');
}
(function setupTabs() {
  const tabs = document.querySelectorAll('.view-tab');
  const panes = document.querySelectorAll('.view-pane');
  setMainView('timeline');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const view = tab.dataset.view;
      tabs.forEach(t => { t.classList.toggle('active', t === tab); });
      panes.forEach(p => { p.classList.toggle('active', p.dataset.view === view); });
      setMainView(view);
      if (view === 'graph') {
        resizeGraph();
        updateGraph();
      } else if (view === 'timeline') {
        scrollHighlightedTimelineStep();
      }
    });
  });
})();

// ── Event handlers ─────────────────────────────────────
function handleEvent(ev) {
  switch (ev.type) {

    case 'session_ready':
      setStatus('connected', 'ready');
      setInputEnabled(true);
      setAgentModel(ev.model_name);
      addRow('dim', 'agent ready.');
      break;

    case 'task_started':
      isRunning = true;
      isSubmitting = false;
      isStopping = false;
      liveSessionId = ev.session_id || null;
      setStatus('running', 'running');
      setInputEnabled(false);
      addSpeaker('user', null);
      addRow('', escHtml(ev.query));
      resetSidebar();
      setSideTask(ev.query);
      break;

    case 'planner_started':
      addRow('dim', 'planner: decomposing task…');
      break;

    case 'planner_completed': {
      const items = ev.subgoals || [];
      if (!items.length) {
        addRow('dim', 'planner: no subgoals.');
      } else {
        const lines = items.map((sg, i) =>
          `<div><span style="color:var(--fg-mute)">${String(i + 1).padStart(2, '0')}</span>  ${escHtml(sg.description)}</div>`
        ).join('');
        addBlock('orange',
          `<div class="title">plan <span class="pill">${items.length}</span></div>${lines}`
        );
      }
      setSubgoals(items);
      break;
    }

    case 'planner_replanning':
      pendingReplanFailedSubgoalId = ev.failed_subgoal_id;
      addRow('warn', `replanning · subgoal ${escHtml(ev.failed_subgoal_id)} failed`);
      break;

    case 'planner_replanned': {
      const items = ev.subgoals || [];
      const lines = items.map((sg, i) =>
        `<div><span style="color:var(--fg-mute)">${String(i + 1).padStart(2, '0')}</span>  ${escHtml(sg.description)}</div>`
      ).join('');
      addBlock('orange',
        `<div class="title">replan <span class="pill">${items.length}</span></div>${lines}`
      );
      replaceSubgoalsAfterFailed(
        ev.failed_subgoal_id != null ? ev.failed_subgoal_id : pendingReplanFailedSubgoalId,
        items
      );
      pendingReplanFailedSubgoalId = null;
      break;
    }

    case 'subgoal_started':
      updateSubgoalStatus(ev.subgoal_id, 'active');
      addRow('', `<span style="color:var(--orange)">▸</span> subgoal ${escHtml(ev.subgoal_id)} <span class="pill running">RUNNING</span> <span class="dim" style="color:var(--fg-dim)">${escHtml(ev.description || '')}</span>`);
      break;

    case 'subgoal_completed':
      updateSubgoalStatus(ev.subgoal_id, 'done');
      addRow('ok', `✓ subgoal ${escHtml(ev.subgoal_id)} <span class="pill done">DONE</span>`);
      break;

    case 'subgoal_failed':
      updateSubgoalStatus(ev.subgoal_id, 'failed');
      addRow('err', `✗ subgoal ${escHtml(ev.subgoal_id)} <span class="pill failed">FAILED</span> ${escHtml(ev.reason || '')}`);
      break;

    case 'replan_error':
      addBlock('red', `<div class="title">replan error</div><div class="meta">${escHtml(ev.error_message || '')}</div>`);
      break;

    case 'step_started':
      metaStep.textContent = `#${ev.step_id}`;
      beginActionStepGroup(ev.step_id);
      addSpeaker('browser-agent', `step ${ev.step_id}`);
      break;

    case 'llm_inference':
      storeLlmInference(ev);
      break;

    case 'reasoning_extracted':
      if (ev.reasoning) {
        addRow('thinking', escHtml(ev.reasoning));
      }
      break;

    case 'function_calls_extracted': {
      const calls = (ev.function_calls || []);
      if (!calls.length) break;
      const phaseCls = phaseForTool(calls[0].name);
      calls.forEach(c => {
        const args = c.args && Object.keys(c.args).length
          ? ` <span class="args">[${escHtml(formatArgs(c.args))}]</span>`
          : '';
        const el = addRow('', `<span style="color:var(--fg-dim)">⚙</span> <span class="tool">${escHtml(c.name)}</span>${args}`);
        if (phaseCls) {
          el.classList.add(phaseCls);
          el.style.paddingLeft = '8px';
          el.style.borderLeft = '2px solid var(--phase-border)';
          el.style.background = 'var(--phase-bg)';
        }
      });
      break;
    }

    case 'review_metadata_extracted': {
      const what = ev.what || ev.action_summary;
      if (!what) break;
      addActivity({
        step: ev.step_id,
        subgoalId: ev.subgoal_id != null ? ev.subgoal_id : null,
        phaseId: ev.phase_id || null,
        what,
        why: ev.why || ev.reason || '',
        outcome: ev.outcome || '',
      });
      break;
    }

    case 'action_executed':
      if (ev.env_state && ev.env_state.url) {
        metaUrl.textContent = ev.env_state.url;
        addRow('dim', `@ <span class="url">${escHtml(ev.env_state.url)}</span>`);
        recordActionExecution(ev);
      }
      if (replayMode && replaySessionId && ev.artifacts && (ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path)) {
        const href = replayArtifactHref(ev.artifacts.after_screenshot_path || ev.artifacts.screenshot_path, 'history');
        addRow('dim', `<a target="_blank" rel="noreferrer" href="${href}">[shot]</a>`);
      }
      break;

    case 'step_error':
      addBlock('red', `<div class="title">error</div><div class="meta">${escHtml(ev.error_message || 'unknown error')}</div>`);
      finishActionStepGroup(ev.step_id);
      break;

    case 'model_request_retry':
      addRow('warn', `~ retry #${escHtml(ev.attempt)} in ${escHtml(ev.delay_seconds)}s`);
      break;

    case 'step_complete':
      if (ev.final_reasoning) {
        addBlock('plain',
          `<div class="title">step complete</div>` +
          `<div class="meta">${escHtml(ev.final_reasoning)}</div>`
        );
      }
      finishActionStepGroup(ev.step_id);
      break;

    case 'task_complete':
      isRunning = false;
      isSubmitting = false;
      isStopping = false;
      clearGraphRunningStep();
      setStatus('connected', 'ready');
      setInputEnabled(true);
      subgoals.forEach(sg => { if (sg.status === 'active') sg.status = 'done'; });
      renderPlan();
      addBlock('green', `<div class="title">task complete</div>`);
      break;

    case 'task_failed':
      isRunning = false;
      isSubmitting = false;
      isStopping = false;
      clearGraphRunningStep();
      setStatus('connected', 'ready');
      setInputEnabled(true);
      subgoals.forEach(sg => { if (sg.status === 'active') sg.status = 'failed'; });
      renderPlan();
      addBlock('red',
        `<div class="title">task failed</div>` +
        `<div class="meta">${escHtml(ev.error_message || 'unknown error')}</div>`
      );
      break;

    case 'task_interrupted':
      isRunning = false;
      isSubmitting = false;
      isStopping = false;
      clearGraphRunningStep();
      setStatus('connected', 'ready');
      setInputEnabled(true);
      subgoals.forEach(sg => { if (sg.status === 'active') sg.status = 'failed'; });
      renderPlan();
      addBlock('orange', `<div class="title">task interrupted</div><div class="meta">${escHtml(ev.reason || 'stopped by user')}</div>`);
      break;

    case 'session_closed':
      clearGraphRunningStep();
      setStatus('disconnected', 'session ended');
      setInputEnabled(false);
      addRow('dim', 'session closed.');
      break;
  }
}

function phaseForTool(name) {
  if (!name) return null;
  if (['navigate','search','go_back','go_forward','open_web_browser'].includes(name)) return 'phase-navigation';
  if (['click_at','click_by_ref','hover_at'].includes(name)) return 'phase-interaction';
  if (['type_text_at','type_by_ref','key_combination','drag_and_drop'].includes(name)) return 'phase-input';
  if (['scroll_at','scroll_document','wait_5_seconds'].includes(name)) return 'phase-observation';
  return 'phase-observation';
}

function formatArgs(obj) {
  return Object.entries(obj)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ── Replay mode ───────────────────────────────────────
function setReplayUi(active) {
  replayMode = active;
  replayBadge.classList.toggle('hidden', !active);
  liveBtn.hidden = !active;
  replayControls.classList.toggle('active', active);
  setInputEnabled(!active && !isRunning && ws && ws.readyState === WebSocket.OPEN);
  if (active) setStatus('connected', 'replay');
}

function replayDelay(prev, next) {
  if (!prev || !next) return 120;
  const speed = replaySpeed.value;
  if (speed === 'instant') return 0;
  const raw = Math.max(40, Math.min(1200, ((next.ts || 0) - (prev.ts || 0)) * 1000));
  return raw / Number(speed || 1);
}

function updateReplayProgress() {
  replaySlider.max = String(Math.max(0, replayEvents.length));
  replaySlider.value = String(replayIndex);
  replayProgress.textContent = `${replayIndex}/${replayEvents.length}`;
}

function dispatchReplayEvent(ev) {
  handleEvent(ev);
  setReplayUi(true);
}

function replayStepForward() {
  if (replayIndex >= replayEvents.length) {
    replayPaused = true;
    updateReplayProgress();
    return;
  }
  const prev = replayEvents[replayIndex - 1];
  const ev = replayEvents[replayIndex];
  replayIndex += 1;
  dispatchReplayEvent(ev);
  updateReplayProgress();
  if (!replayPaused) {
    const next = replayEvents[replayIndex];
    replayTimer = setTimeout(replayStepForward, replayDelay(prev || ev, next || ev));
  }
}

function replayTo(index) {
  clearTimeout(replayTimer);
  replayPaused = true;
  const target = Math.max(0, Math.min(index, replayEvents.length));
  resetTimeline();
  resetSidebar();
  setReplayUi(true);
  replayIndex = 0;
  while (replayIndex < target) replayStepForward();
  replayPaused = true;
  updateReplayProgress();
}

async function loadSessions() {
  sessionsList.innerHTML = '<div class="session-item"><span class="meta">loading…</span></div>';
  const res = await fetch('/sessions');
  const data = await res.json();
  const sessions = data.sessions || [];
  if (!sessions.length) {
    sessionsList.innerHTML = '<div class="session-item"><span class="meta">no saved sessions</span></div>';
    return;
  }
  sessionsList.innerHTML = '';
  sessions.forEach(session => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'session-item icon-label';
    const query = session.query || 'unknown task';
    btn.innerHTML =
      `<svg class="btn-icon" aria-hidden="true" viewBox="0 0 24 24" focusable="false">` +
        `<path d="M8 5v14l11-7z"></path>` +
      `</svg>` +
      `<span><span>${escHtml(session.id)} · “${escHtml(query.slice(0, 80))}”</span>` +
      `<div class="meta">${escHtml(session.step_count || 0)} steps · ${session.has_events ? 'events' : 'synthetic'}${session.model ? ' · ' + escHtml(session.model) : ''}</div></span>`;
    btn.addEventListener('click', () => startReplay(session.id));
    sessionsList.appendChild(btn);
  });
}

async function startReplay(sessionId) {
  const res = await fetch(`/sessions/${encodeURIComponent(sessionId)}/events`);
  const data = await res.json();
  replaySessionId = sessionId;
  replayEvents = data.events || [];
  replayIndex = 0;
  replayPaused = true;
  resetTimeline();
  resetSidebar();
  setReplayUi(true);
  updateReplayProgress();
  sessionsPanel.classList.add('hidden');
}

sessionsBtn.addEventListener('click', () => {
  sessionsPanel.classList.toggle('hidden');
  if (!sessionsPanel.classList.contains('hidden')) loadSessions();
});
sessionsClose.addEventListener('click', () => sessionsPanel.classList.add('hidden'));
liveBtn.addEventListener('click', () => {
  clearTimeout(replayTimer);
  replayPaused = true;
  replayEvents = [];
  replayIndex = 0;
  replaySessionId = null;
  resetTimeline();
  resetSidebar();
  setReplayUi(false);
  setStatus(ws && ws.readyState === WebSocket.OPEN ? 'connected' : 'disconnected', ws && ws.readyState === WebSocket.OPEN ? 'ready' : 'disconnected');
});
replayPlay.addEventListener('click', () => {
  replayPaused = !replayPaused;
  clearTimeout(replayTimer);
  if (!replayPaused) replayStepForward();
});
replayNext.addEventListener('click', () => {
  replayPaused = true;
  clearTimeout(replayTimer);
  replayStepForward();
});
replayPrev.addEventListener('click', () => replayTo(Math.max(0, replayIndex - 1)));
replaySlider.addEventListener('input', () => replayTo(Number(replaySlider.value || 0)));

// ── Task submission ────────────────────────────────────
async function submitTask() {
  const query = input.value.trim();
  if (!query || isRunning || isSubmitting) return;
  input.value = '';
  autoResize();
  isSubmitting = true;
  isStopping = false;
  setStatus('running', 'submitting…');
  setInputEnabled(false);
  try {
    const res = await fetch('/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    isSubmitting = false;
    setStatus(ws && ws.readyState === WebSocket.OPEN ? 'connected' : 'disconnected', ws && ws.readyState === WebSocket.OPEN ? 'ready' : 'disconnected');
    setInputEnabled(ws && ws.readyState === WebSocket.OPEN && !replayMode);
    addBlock('red', `<div class="title">network error</div><div class="meta">failed to submit task. is the server running?</div>`);
  }
}

async function interruptTask() {
  if ((!isRunning && !isSubmitting) || isStopping) return;
  isStopping = true;
  updateControlStates();
  setStatus('running', 'stopping…');
  addRow('warn', 'interrupt requested…');
  try {
    const res = await fetch('/interrupt', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    isStopping = false;
    updateControlStates();
    addBlock('red', `<div class="title">network error</div><div class="meta">failed to interrupt task. is the server running?</div>`);
  }
}

btn.addEventListener('click', () => {
  if (isRunning || isSubmitting) {
    interruptTask();
  } else {
    submitTask();
  }
});

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    submitTask();
  }
});

function autoResize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
}
input.addEventListener('input', autoResize);

setupTheme();
connect();

// ── Sidebar resize ─────────────────────────────────────
(function setupResizer() {
  const resizer = document.getElementById('resizer');
  if (!resizer) return;
  const MIN = 220, MAX = 720;
  const KEY = 'bragent.asideW';

  const saved = parseInt(localStorage.getItem(KEY) || '', 10);
  if (saved && saved >= MIN && saved <= MAX) {
    document.body.style.setProperty('--aside-w', saved + 'px');
  }

  let dragging = false;
  resizer.addEventListener('pointerdown', (e) => {
    dragging = true;
    resizer.setPointerCapture(e.pointerId);
    document.body.classList.add('resizing');
    e.preventDefault();
  });
  resizer.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const w = Math.min(MAX, Math.max(MIN, window.innerWidth - e.clientX));
    document.body.style.setProperty('--aside-w', w + 'px');
  });
  const stop = (e) => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('resizing');
    try { resizer.releasePointerCapture(e.pointerId); } catch (_) {}
    const cur = getComputedStyle(document.body).getPropertyValue('--aside-w').trim();
    const px = parseInt(cur, 10);
    if (px) localStorage.setItem(KEY, String(px));
  };
  resizer.addEventListener('pointerup', stop);
  resizer.addEventListener('pointercancel', stop);
  resizer.addEventListener('dblclick', () => {
    document.body.style.setProperty('--aside-w', '340px');
    localStorage.setItem(KEY, '340');
  });
})();
