# Graph Attention Cues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DG2 attention cues (loop / revisit / dead-end badges with own + rollup severity) to each node in the existing drilldown graph, so reviewers can spot structural failure topology at a glance without drilling in.

**Architecture:** All changes are additive and local to three files (`src/ui/static/graph.js`, `src/ui/static/panel.css`, `tests/test_ui_panel.py`). New pure helpers compute cue flags per render; a new `<g class="node-cue-badge">` group is appended to each node with severity-driven CSS class; the existing `showTooltip` is extended with a cue breakdown section. The drilldown layout, force simulation, sequence tracking, and viridis fill/radius encodings are not touched.

**Tech Stack:** Vanilla JS + d3 v7 (already in panel), Python pytest (string-contract tests against concatenated HTML/CSS/JS).

**Spec:** `docs/superpowers/specs/2026-05-21-graph-attention-cues-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/ui/static/graph.js` | Modify | Add `urlSequence` tracking, `computeOwnCues` / `buildCueContext` / `rollupCueFor` helpers, attach cue fields in `buildUrlGraphData` / `buildViewportGraphData` / `buildActionGraphData`, render `<g class="node-cue-badge">` in `graph.update`, extend `showTooltip` with cue breakdown. |
| `src/ui/static/panel.css` | Modify | Add `.node-cue-badge` rules: `circle.own-red`, `circle.own-gray`, `circle.rollup-red`, badge text styling. |
| `tests/test_ui_panel.py` | Modify | Add 5 contract tests asserting helper presence, severity matrix, badge hide/show guard, and tooltip extension. |

---

### Task 1: Record global URL navigation sequence

`computeOwnCues` needs an ordered list of URL visits to detect URL-layer loop/revisit. Add it as a module-level array, populate it in `recordNavigation`, and reset it alongside other trajectory state.

**Files:**
- Modify: `src/ui/static/graph.js` (state block at top, `resetTrajectoryGraphState`, `recordNavigation`)
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

Add at the end of `tests/test_ui_panel.py`:

```python
def test_panel_graph_tracks_global_url_sequence():
    # Global URL nav order is needed for layer-1 cue detection.
    assert "let urlSequence = [];" in PANEL_HTML
    record_nav = PANEL_HTML.split("function recordNavigation(url, stepId)", 1)[1].split(
        "function recordActionExecution", 1
    )[0]
    assert "urlSequence.push(key);" in record_nav
    reset_fn = PANEL_HTML.split("function resetTrajectoryGraphState()", 1)[1].split(
        "function ", 1
    )[0]
    assert "urlSequence.length = 0;" in reset_fn or "urlSequence = [];" in reset_fn
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_tracks_global_url_sequence -v
```

Expected: FAIL — `assert "let urlSequence = [];" in PANEL_HTML` is false.

- [ ] **Step 3: Add state, reset, and recording**

In `src/ui/static/graph.js`:

Below `let actionNodeIdByStep = new Map();` add:

```js
let urlSequence = [];
```

In `resetTrajectoryGraphState()` body, alongside the other `.clear()` lines, add:

```js
urlSequence.length = 0;
```

In `recordNavigation(url, stepId)`, immediately after `trajectoryLastKey = key;` (the line that records the most-recent URL), add:

```js
urlSequence.push(key);
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_tracks_global_url_sequence -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Track global URL navigation sequence for cue detection"
```

---

### Task 2: `computeOwnCues` helper — per-node loop/revisit/dead-end

Pure function returning `{ loop, revisit, deadEnd, severity }` for one node at one layer. Uniformly sequence-based across all three layers (URL uses the global `urlSequence`, viewport uses `parentUrl.viewportSequence`, action uses `parentViewport.actionSequence`).

**Files:**
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_compute_own_cues_handles_all_three_layers():
    assert "function computeOwnCues(type, node, sequence)" in PANEL_HTML
    body = PANEL_HTML.split("function computeOwnCues(type, node, sequence)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # All three cue keys present in returned shape
    assert "loop:" in body
    assert "revisit:" in body
    assert "deadEnd:" in body
    # Severity logic: red wins over gray; none when no cues
    assert "loop || revisit" in body
    assert "'red'" in body
    assert "'gray'" in body
    assert "'none'" in body
    # Sequence helpers used (consecutive dup for loop, non-consecutive occurrence for revisit)
    assert "sequence[i - 1] === node.id" in body or "seq[i - 1] === node.id" in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_compute_own_cues_handles_all_three_layers -v
```

Expected: FAIL — function not defined.

- [ ] **Step 3: Implement `computeOwnCues`**

In `src/ui/static/graph.js`, **immediately after** `function actionStepCountForActionIds(actionIds) { ... }` (or any stable anchor before `function recordNavigation`), add:

```js
function computeOwnCues(type, node, sequence) {
  let loop = false;
  let revisit = false;
  let deadEnd = false;
  const seq = sequence || [];
  let seen = false;
  for (let i = 0; i < seq.length; i++) {
    if (seq[i] !== node.id) continue;
    if (i > 0 && seq[i - 1] === node.id) loop = true;
    if (seen && (i === 0 || seq[i - 1] !== node.id)) revisit = true;
    seen = true;
  }
  if (seq.length > 0 && seq[seq.length - 1] === node.id) deadEnd = true;
  const severity = (loop || revisit) ? 'red' : (deadEnd ? 'gray' : 'none');
  return { loop, revisit, deadEnd, severity };
}
```

(`type` is unused at this layer of abstraction — the per-layer wiring picks the right sequence — but kept in the signature so future per-layer rules can branch without changing call sites.)

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_compute_own_cues_handles_all_three_layers -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Add computeOwnCues helper for loop/revisit/dead-end detection"
```

---

### Task 3: Rollup walker

Compute `{ rollupCount, rollupSeverity, rollupBreakdown }` for a node by scanning its descendants' own cues. **Excludes dead-end from rollup** per spec.

**Files:**
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_rollup_excludes_dead_end():
    assert "function buildCueContext()" in PANEL_HTML
    assert "function rollupCueFor(type, scope, context)" in PANEL_HTML
    body = PANEL_HTML.split("function rollupCueFor(type, scope, context)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # rollup counts loop/revisit only; deadEnd is intentionally not added
    assert "cues.loop || cues.revisit" in body
    assert "cues.deadEnd" not in body  # dead-end never contributes to rollup
    # rollupSeverity is binary: 'red' or 'none'
    assert "'red'" in body
    assert "'none'" in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_rollup_excludes_dead_end -v
```

Expected: FAIL — functions not defined.

- [ ] **Step 3: Implement `buildCueContext` and `rollupCueFor`**

In `src/ui/static/graph.js`, immediately after `computeOwnCues`, add:

```js
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
  return { ownCuesById };
}

function rollupCueFor(type, scope, context) {
  let count = 0;
  let hasRed = false;
  const breakdown = { loop: 0, revisit: 0 };
  const tally = (id) => {
    const cues = context.ownCuesById.get(id);
    if (!cues) return;
    if (cues.loop || cues.revisit) {
      count += 1;
      hasRed = true;
      if (cues.loop) breakdown.loop += 1;
      if (cues.revisit) breakdown.revisit += 1;
    }
  };
  if (type === 'url') {
    for (const vpId of scope.viewportIds || []) {
      tally(vpId);
      const vp = trajectoryViewports.get(vpId);
      if (vp) for (const actId of vp.actionIds || []) tally(actId);
    }
  } else if (type === 'viewport') {
    for (const actId of scope.actionIds || []) tally(actId);
  }
  return { rollupCount: count, rollupSeverity: hasRed ? 'red' : 'none', rollupBreakdown: breakdown };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_rollup_excludes_dead_end -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Add rollup walker for descendant cue aggregation"
```

---

### Task 4: Wire cue fields into the three layer builders

`buildUrlGraphData`, `buildViewportGraphData`, `buildActionGraphData` each attach `{ ownCues, ownSeverity, rollupCount, rollupSeverity, rollupBreakdown, badgeCount }` to every node they return.

**Files:**
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_builders_attach_cue_fields():
    for fn in ("buildUrlGraphData", "buildViewportGraphData", "buildActionGraphData"):
        body = PANEL_HTML.split(f"function {fn}", 1)[1].split(
            "\nfunction ", 1
        )[0]
        assert "computeOwnCues" in body, f"{fn} must compute own cues"
        assert "rollupCueFor" in body, f"{fn} must compute rollup"
        assert "badgeCount" in body, f"{fn} must derive badgeCount"
    # badgeCount formula: own contributes 1 when not 'none', plus rollupCount
    assert "(ownSeverity !== 'none' ? 1 : 0) + rollupCount" in PANEL_HTML
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_builders_attach_cue_fields -v
```

Expected: FAIL — builders don't reference these helpers yet.

- [ ] **Step 3: Modify the three builders**

In `buildUrlGraphData`, **before** the `nodes.map(...)` call, add:

```js
const cueContext = buildCueContext();
```

Then inside the `.map(src => ({ ... }))` returning each node, add these fields:

```js
...(() => {
  const own = computeOwnCues('url', src, urlSequence);
  const rollup = rollupCueFor('url', src, cueContext);
  const badgeCount = (own.severity !== 'none' ? 1 : 0) + rollup.rollupCount;
  return {
    ownCues: own, ownSeverity: own.severity,
    rollupCount: rollup.rollupCount,
    rollupSeverity: rollup.rollupSeverity,
    rollupBreakdown: rollup.rollupBreakdown,
    badgeCount,
  };
})(),
```

Repeat the same pattern in `buildViewportGraphData` (use `'viewport'` and `cueContext` built once at top of the function; pass `urlNode.viewportSequence` as the sequence), and in `buildActionGraphData` (use `'action'`; pass `viewportNode.actionSequence`; rollup will always be 0 for actions since `rollupCueFor` returns 0 for non-`url`/`viewport` types).

To keep the diff minimal and DRY, extract the per-node attachment into a helper before the builders:

```js
function attachCueFields(type, src, sequence, context) {
  const own = computeOwnCues(type, src, sequence);
  const rollup = rollupCueFor(type, src, context);
  const badgeCount = (own.severity !== 'none' ? 1 : 0) + rollup.rollupCount;
  return {
    ownCues: own,
    ownSeverity: own.severity,
    rollupCount: rollup.rollupCount,
    rollupSeverity: rollup.rollupSeverity,
    rollupBreakdown: rollup.rollupBreakdown,
    badgeCount,
  };
}
```

Then each builder's node-map merges `...attachCueFields(type, src, sequence, cueContext)` into the returned object.

Verify the test's literal assertion `"(ownSeverity !== 'none' ? 1 : 0) + rollupCount"` matches the string in the file (inside `attachCueFields`).

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_builders_attach_cue_fields -v
```

Expected: PASS.

- [ ] **Step 5: Run all UI panel tests to check no regression**

```bash
uv run pytest tests/test_ui_panel.py -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Attach own + rollup cue fields to graph nodes"
```

---

### Task 5: CSS for the badge

Three node-cue-badge circle variants plus shared text styling. Explicitly no `rollup-gray` class.

**Files:**
- Modify: `src/ui/static/panel.css`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_cue_badge_css_present():
    assert ".node-cue-badge circle.own-red" in PANEL_HTML
    assert ".node-cue-badge circle.own-gray" in PANEL_HTML
    assert ".node-cue-badge circle.rollup-red" in PANEL_HTML
    # dead-end is excluded from rollup → no rollup-gray class
    assert ".node-cue-badge circle.rollup-gray" not in PANEL_HTML
    assert ".node-cue-badge text" in PANEL_HTML
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_cue_badge_css_present -v
```

Expected: FAIL — classes don't exist yet.

- [ ] **Step 3: Add CSS**

In `src/ui/static/panel.css`, append at the end of the graph-related block (right after the `.graph-tooltip .tt-row .v { color: var(--fg); }` rule that already exists):

```css
.node-cue-badge { cursor: pointer; }
.node-cue-badge circle.own-red    { fill: var(--md-sys-color-error); stroke: none; }
.node-cue-badge circle.own-gray   { fill: var(--fg-mute);            stroke: none; }
.node-cue-badge circle.rollup-red {
  fill: var(--surface-1);
  stroke: var(--md-sys-color-error);
  stroke-width: 1.5;
}
.node-cue-badge text {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
}
.node-cue-badge text.on-fill   { fill: white; }
.node-cue-badge text.on-stroke { fill: var(--md-sys-color-error); }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_cue_badge_css_present -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/static/panel.css tests/test_ui_panel.py
git commit -m "[feat] Add CSS for node cue badge (own/rollup, red/gray)"
```

---

### Task 6: Render the badge in the d3 update path

Append `<g class="node-cue-badge">` (with `<circle>` + `<text>`) to every graph node on enter. On update, hide if `badgeCount === 0`, otherwise position at top-right, set severity class, write count text.

**Files:**
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_renders_cue_badge_with_severity_matrix():
    update_body = PANEL_HTML.split("function update(payload) {", 1)[1].split(
        "function reset()", 1
    )[0]
    # Badge group is attached on enter
    assert ".node-cue-badge" in update_body
    assert "g').attr('class', 'node-cue-badge'" in update_body or 'class\', \'node-cue-badge\'' in update_body
    # Badge visibility gated on badgeCount > 0
    assert "d.badgeCount > 0" in update_body or "d.badgeCount >= 1" in update_body
    # Severity matrix: own-red > rollup-red > own-gray, plus hidden state
    assert "own-red" in update_body
    assert "own-gray" in update_body
    assert "rollup-red" in update_body
    # Text class toggles between on-fill (filled badge) and on-stroke (outlined)
    assert "on-fill" in update_body
    assert "on-stroke" in update_body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_renders_cue_badge_with_severity_matrix -v
```

Expected: FAIL — renderer doesn't touch `.node-cue-badge` yet.

- [ ] **Step 3: Helper + enter selection**

In `src/ui/static/graph.js`, **inside** the `graph` IIFE (anywhere before `function update(payload)`), add this helper:

```js
function cueBadgeClass(d) {
  if (!d || !d.badgeCount) return { circleClass: null, textClass: null, hidden: true };
  if (d.ownSeverity === 'red')                                return { circleClass: 'own-red',    textClass: 'on-fill',   hidden: false };
  if (d.rollupSeverity === 'red')                              return { circleClass: 'rollup-red', textClass: 'on-stroke', hidden: false };
  if (d.ownSeverity === 'gray')                                return { circleClass: 'own-gray',   textClass: 'on-fill',   hidden: false };
  return { circleClass: null, textClass: null, hidden: true };
}
```

In `function update(payload) { ... }`, locate the existing node-enter block (the one that does `enter.append('circle').attr('r', 8); enter.append('text')...`). Right after those two lines and before the `nodeSel = enter.merge(nodeSel);` line, add:

```js
const badgeEnter = enter.append('g').attr('class', 'node-cue-badge');
badgeEnter.append('circle').attr('r', 8);
badgeEnter.append('text');
```

After `nodeSel = enter.merge(nodeSel);` and after the existing per-node attribute updates (the `.classed(...)` chain), add the badge update:

```js
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_renders_cue_badge_with_severity_matrix -v
```

Expected: PASS.

- [ ] **Step 5: Run all UI panel tests**

```bash
uv run pytest tests/test_ui_panel.py -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Render cue badge group with severity-driven class"
```

---

### Task 7: Extend `showTooltip` with cue breakdown

When a node has any cue (own or rollup), append a "Cues" section to the tooltip with per-type "own / inside" counts. Zero-count rows suppressed; the section is omitted entirely if everything is zero.

**Files:**
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_panel_graph_tooltip_includes_cue_breakdown():
    tooltip_block = PANEL_HTML.split("function showTooltip(event, d) {", 1)[1].split(
        "function moveTooltip(event)", 1
    )[0]
    # Section header + per-type rows
    assert "Cues" in tooltip_block
    assert "loop" in tooltip_block
    assert "revisit" in tooltip_block
    assert "dead-end" in tooltip_block
    # own / inside split
    assert "own" in tooltip_block
    assert "inside" in tooltip_block
    # Guarded: only renders when something to show
    assert "d.badgeCount" in tooltip_block or "d.ownCues" in tooltip_block
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_tooltip_includes_cue_breakdown -v
```

Expected: FAIL — tooltip doesn't mention cues yet.

- [ ] **Step 3: Modify `showTooltip`**

In `src/ui/static/graph.js`, inside `function showTooltip(event, d) { ... }`, **before** the final `tooltip.innerHTML = ...` line, add:

```js
const cueRows = [];
if (d && d.ownCues) {
  const own = d.ownCues;
  const inside = d.rollupBreakdown || { loop: 0, revisit: 0 };
  const loopOwn = own.loop ? 1 : 0;
  const revisitOwn = own.revisit ? 1 : 0;
  const deadEndOwn = own.deadEnd ? 1 : 0;
  if (loopOwn || inside.loop)       cueRows.push(`<div class="tt-row"><span>loop</span><span class="v">${loopOwn} own / ${inside.loop} inside</span></div>`);
  if (revisitOwn || inside.revisit) cueRows.push(`<div class="tt-row"><span>revisit</span><span class="v">${revisitOwn} own / ${inside.revisit} inside</span></div>`);
  if (deadEndOwn)                   cueRows.push(`<div class="tt-row"><span>dead-end</span><span class="v">${deadEndOwn} own / 0 inside</span></div>`);
}
const cueSection = cueRows.length
  ? `<div class="tt-section">Cues</div>` + cueRows.join('')
  : '';
```

Then change the `tooltip.innerHTML = ...` assignment to concatenate `cueSection` at the end of the existing rows string. For example, if the existing line is:

```js
tooltip.innerHTML = `<div class="tt-url">${escHtml(title)}</div>` + rows.join('');
```

change it to:

```js
tooltip.innerHTML = `<div class="tt-url">${escHtml(title)}</div>` + rows.join('') + cueSection;
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_tooltip_includes_cue_breakdown -v
```

Expected: PASS.

- [ ] **Step 5: Run all UI panel tests**

```bash
uv run pytest tests/test_ui_panel.py -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "[feat] Extend graph tooltip with cue breakdown section"
```

---

### Task 8: Manual smoke test in the live UI

Static-string tests can't verify the badge actually paints. Launch the UI, drive a short trajectory that produces all three cue types, and visually confirm.

**Files:** none modified.

- [ ] **Step 1: Start the panel**

```bash
uv run main.py --ui
```

The panel opens at http://localhost:8765.

- [ ] **Step 2: Drive a trajectory that hits all three cues**

In the panel's task input, run a query that will reasonably produce:
- A URL loop: e.g., "navigate to https://example.com, then navigate to https://example.com again"
- A revisit: e.g., "go to google.com, then bing.com, then back to google.com"
- A dead-end: whatever the last URL is naturally becomes the dead-end

A single query like `"go to https://example.com, then to https://www.iana.org, then back to https://example.com, then refresh"` should hit all three on the URL layer.

- [ ] **Step 3: Open the Graph view**

Click the Graph tab. Confirm visually for each layer (URL → drill into Viewport → drill into Action):
- Nodes with own loop/revisit show a **filled red** badge in the top-right with a count.
- The terminal URL/viewport/action shows a **filled gray** badge.
- A URL whose internal viewports/actions have loops shows a **white-fill red-outlined** badge.
- Clean nodes show **no badge**.

- [ ] **Step 4: Hover a badged node**

Confirm the tooltip now has a `Cues` section with `loop / revisit / dead-end` rows formatted as `N own / M inside`.

- [ ] **Step 5: No commit**

This task is verification only.

---

## Self-Review

**Spec coverage check:** Every Section-1/3/4/5/6 requirement in the spec maps to a task above:

| Spec section | Task |
|---|---|
| 3. Definitions (per-layer loop/revisit/dead-end) | Task 2 (computeOwnCues, sequence-based for all 3 layers — uniform & equivalent to spec's per-layer rules) |
| 3.1 Rollup (excludes dead-end) | Task 3 (rollupCueFor; test explicitly asserts deadEnd is not referenced) |
| 3.2 badgeCount formula | Task 4 (test asserts the literal formula string) |
| 4.1 Badge geometry & placement | Task 6 (translate `(r+4, -(r+4))`, circle r=8 base / 10 when count ≥10) |
| 4.2 Color rules / severity matrix | Task 6 (cueBadgeClass function, all 4 matrix rows + hidden state) |
| 4.3 Tooltip extension | Task 7 (Cues section with per-type own/inside) |
| 4.4 Interaction (badge inherits node click) | Task 5 CSS (`cursor: pointer`); badge group is a child of graph-node so existing click handlers fire — no extra wiring needed |
| 4.5 Per-layer behavior | Task 4 (all 3 builders attach cues) |
| 5.1 / 5.2 / 5.3 Implementation outline | Tasks 1–7 follow the outline 1:1 |
| 6. Testing (4 contract tests) | Tasks 2, 4, 5, 6, 7 each add one test; Task 3 adds the rollup-exclusion test |

**Placeholder scan:** No "TBD" / "TODO" / "appropriate" / "as needed" in any step. Every code step shows the exact code to write.

**Type consistency:** Function and field names are stable across tasks: `computeOwnCues(type, node, sequence)` returns `{ loop, revisit, deadEnd, severity }`; `rollupCueFor(type, scope, context)` returns `{ rollupCount, rollupSeverity, rollupBreakdown }`; node objects gain `{ ownCues, ownSeverity, rollupCount, rollupSeverity, rollupBreakdown, badgeCount }`. The CSS class names `own-red` / `own-gray` / `rollup-red` are referenced identically in Tasks 5, 6, 7. The `cueBadgeClass` helper (Task 6) consumes the field names produced in Task 4.

**Note on a minor deviation from spec:** The spec describes URL loop detection via `trajectoryEdges` self-edge. The plan uses sequence-based detection uniformly across all three layers (URL uses `urlSequence`, viewport uses `viewportSequence`, action uses `actionSequence`). The two are equivalent — `trajectoryEdges` is built from sequential pairs in `recordNavigation`, so a URL self-edge exists iff `urlSequence` has two consecutive identical entries. The uniform approach is simpler and lets `computeOwnCues` be one function instead of three. Worth a sentence in the design doc on follow-up; not material for implementation.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-21-graph-attention-cues.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
