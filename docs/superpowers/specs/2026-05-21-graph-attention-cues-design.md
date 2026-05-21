# Graph Attention Cues for Structural Failures — Design

**Date:** 2026-05-21
**Scope:** `src/ui/static/graph.js`, `src/ui/static/panel.css`, `tests/test_ui_panel.py`
**Related design goal:** DG2 — Structural-failure visibility (loop / revisit / dead-end as reviewer attention cues, never auto-judgment).

## 1. Problem

Today's Graph Vis surfaces *quantity* of work per node (viridis fill scaled by action-step count, radius scaled by visits) but does not surface *topological structure*. A reviewer staring at the URL layer cannot tell whether a node represents a clean linear pass, a loop, a returned-to revisit, or the trajectory's terminal — they have to drill in and read the sequence.

Because each layer dedupes nodes by identity (URL key, viewport `size|scroll`, action signature), repeats collapse into a single circle and the *graph topology* that exposes structural failure is invisible.

## 2. Goal

Make loop / revisit / dead-end visible at every layer as **attention cues** — small visual markers that say "look here," never "this failed." Reviewer judgment stays the source of truth.

Non-goals:
- No automatic classification of trajectory success/failure.
- No new layout algorithm. The existing drill-down (URL → Viewport → Action) is preserved.
- No change to existing color (viridis fill) or size (radius) encodings.

## 3. Definitions

For a given node `n` at a given layer, the three cue flags are computed from the ordered sequence for that layer:

- URL layer: global URL visit sequence.
- Viewport layer: parent URL's `viewportSequence`.
- Action layer: parent viewport's `actionSequence`.

| Layer | Loop (own) | Revisit (own) | Dead-end (own) |
|---|---|---|---|
| URL | global URL sequence has `n.id` appearing in two consecutive positions | `n.id` appears more than once with at least one different URL between occurrences | `n.id` is the middle node in a bounce-back pattern: `A -> n -> A`, where `A !== n` |
| Viewport | parent URL's `viewportSequence` has `n.id` appearing in two consecutive positions | `n.id` appears more than once with at least one different viewport between occurrences | `n.id` is the middle node in a bounce-back pattern inside the parent URL: `A -> n -> A`, where `A !== n` |
| Action | parent viewport's `actionSequence` has `n.id` appearing in two consecutive positions | `n.id` appears more than once with at least one different action between occurrences | `n.id` is the middle node in a bounce-back pattern inside the parent viewport: `A -> n -> A`, where `A !== n` |

A node that has *only* a self-loop is **not** counted as a revisit. This keeps the same physical event from being double-counted across two cue types.

Dead-end is no longer the terminal node in a sequence. It marks the branch that the agent entered and immediately backed out of. In `A -> B -> A`, `B` is the dead-end and `A` is not.

The current final node in a sequence is not a dead-end by itself. If reviewers need that marker later, it should be introduced as a separate `terminal` or `current-end` cue instead of overloading `dead-end`.

### 3.1 Rollup

`rollupCount(n)` = number of *distinct descendant nodes* (across all deeper layers) whose own-cue set contains **loop or revisit**. Dead-end remains excluded from rollup because it is a local branch-shape clue; propagating it upward would make parent nodes look suspicious even when the only issue is a small bounced subpath that the reviewer can inspect after drilling in.

Action nodes are leaves and have rollup = 0.

`rollupSeverity(n)` ∈ {`none`, `red`}:
- `red` if any descendant has loop or revisit
- `none` otherwise

(There is no `rollup-gray` state — see the trade-off in Section 7.)

`ownSeverity(n)` ∈ {`none`, `gray`, `red`} applies the severity rule to `n` itself:
- `red` if `n` has loop or revisit (dead-end may co-exist)
- `gray` if `n` has only dead-end
- `none` otherwise

### 3.2 Badge count

The number rendered inside the badge is:

```
badgeCount(n) = (ownSeverity(n) !== 'none' ? 1 : 0) + rollupCount(n)
```

This is the number of *nodes* the reviewer would need to inspect — including `n` itself when its own cues are non-empty. It is intentionally not a count of cue events (which would double-count repeated revisits).

## 4. Visual contract

### 4.1 Badge geometry

- One badge per node, attached to the node's `<g class="graph-node">` as a sibling `<g class="node-cue-badge">`.
- Placement: top-right of the node circle. Translate by `(r + 4, -(r + 4))` where `r` is the rendered node radius.
- Shape: circle, radius 8px by default and 10px when count ≥ 10.
- Text inside: monospace, 9px, count as integer. No cap; if the number is large the badge widens to fit.

### 4.2 Color rules

Severity = `max(ownSeverity, rollupSeverity)` decides the color. Whether own or rollup carries the cue decides fill vs outline.

Badge color = the *strongest* severity present at the node (own or rollup). Fill vs stroke = where that strongest severity lives.

| ownSeverity | rollupSeverity | Badge style |
|---|---|---|
| red | any | filled red, white text |
| gray | red | white fill, red 1.5px stroke, red text (rollup loop/revisit wins over own dead-end) |
| gray | none | filled gray, white text |
| none | red | white fill, red 1.5px stroke, red text |
| none | none | badge hidden (no DOM) |

`red` uses `var(--md-sys-color-error)`. `gray` uses `var(--fg-mute)`.

Rationale: loop/revisit signal "something might be wrong here" and earn red. Dead-end is a local bounced-branch marker and earns muted gray so reviewers can spot it without letting it compete with stronger loop/revisit alarms.

### 4.3 Tooltip extension

The badge does not own its own tooltip. The existing node tooltip (`showTooltip` in graph.js) gains a `cues` section, rendered only when the node has any cue (own or rollup):

```
[node header — existing]
…
Cues
• loop:     1 own / 0 inside
• revisit:  0 own / 2 inside
• dead-end: 1 own / 0 inside
```

Zero-count rows are suppressed; sections with all zeros disappear entirely.

### 4.4 Interaction

Clicking the badge selects the underlying node (same as clicking the circle). No new keyboard shortcuts, no drag handle on the badge. The badge has `pointer-events: all` so it doesn't blackhole hover from the circle below.

### 4.5 Per-layer behavior

- **URL drill-down view**: each URL node carries own (URL-level cues) + rollup (cues found in its viewports and actions).
- **Viewport drill-down view**: each viewport node carries own (viewport-level cues) + rollup (cues in its actions).
- **Action drill-down view**: each action node carries own only; rollup is always 0 (leaf).

The drill-down root (parent context) node uses the same rules.

## 5. Implementation outline

All changes are confined to two source files plus tests.

### 5.1 `src/ui/static/graph.js`

1. **Helper `computeOwnCues(type, node, sequence)`** — given a graph data object and the ordered sequence for its layer, returns `{ loop, revisit, deadEnd, severity }`.
   - Pure function over the passed sequence and node id. No new persistent state beyond the existing sequence tracking.
   - Dead-end detection scans the sequence for `seq[i - 1] === seq[i + 1] && seq[i] !== seq[i - 1] && seq[i] === node.id`.
2. **Cue context + rollup walker** — `buildCueContext()` computes own cues for URLs, viewports, and actions. `rollupCueFor(type, scope, context)` then scans descendants for loop/revisit cues. For URL nodes, iterate `viewportIds → actionIds` and accumulate descendant cue counts and severities. For viewport nodes, iterate `actionIds`.
3. **Node attachment helper** — `attachCueFields(type, src, sequence, context)` attaches `{ ownCues, ownSeverity, rollupCount, rollupSeverity, rollupBreakdown, badgeCount }` to every node returned from `buildUrlGraphData`, `buildViewportGraphData`, and `buildActionGraphData`.
4. **Renderer** — in the `update(payload)` function:
   - Enter selection appends `<g class="node-cue-badge">` containing `<circle>` and `<text>`.
   - Update step toggles visibility based on `badgeCount > 0`, sets fill/stroke class according to the severity matrix, writes the count text, and translates by `(r + 4, -(r + 4))`.
   - Exit removes the badge group.
5. **Tooltip extension** — `showTooltip` gains a cue-section block guarded by `if (d.ownCues)`.

### 5.2 `src/ui/static/panel.css`

New CSS block (~30 lines):

```css
.node-cue-badge circle.own-red    { fill: var(--md-sys-color-error); stroke: none; }
.node-cue-badge circle.own-gray   { fill: var(--fg-mute);            stroke: none; }
.node-cue-badge circle.rollup-red {
  fill: var(--surface-1); stroke: var(--md-sys-color-error); stroke-width: 1.5;
}
.node-cue-badge text {
  font-family: var(--mono); font-size: 9px; font-weight: 700;
  text-anchor: middle; dominant-baseline: central; pointer-events: none;
}
.node-cue-badge text.on-fill   { fill: white; }
.node-cue-badge text.on-stroke { fill: var(--md-sys-color-error); }
.node-cue-badge { cursor: pointer; }
```

### 5.3 Data flow

```
event → recordActionExecution
       ↓ (existing: trajectoryNodes / Viewports / Actions / sequences updated)
       ↓
buildXxxGraphData()
  ├─ existing node assembly
  └─ attachCueFields(type, src, sequence, context)  ← render-time only
       ↓ each node gains { ownCues, ownSeverity, rollupCount, rollupSeverity, rollupBreakdown }
       ↓
graph.update(payload)
  └─ for each node enter/update: render <g class="node-cue-badge"> if badgeCount > 0
```

No new fields on the persistent trajectory maps. All cue computation is render-time.

## 6. Testing

New contract tests in `tests/test_ui_panel.py`:

1. **`test_panel_graph_compute_own_cues_handles_all_three_layers`** — asserts `computeOwnCues` exists and verifies the loop/revisit/deadEnd flag keys exist in the output shape.
2. **`test_panel_graph_dead_end_uses_bounce_back_not_terminal`** — asserts dead-end is detected from a `seq[i - 1] === seq[i + 1]` style bounce-back check and that the old terminal-only condition (`seq[seq.length - 1] === node.id`) is not used to set `deadEnd`.
3. **`test_panel_graph_renders_cue_badge_with_severity_color`** — `.node-cue-badge` group present in the render path; the three CSS class names (`own-red`, `own-gray`, `rollup-red`) exist in the stylesheet (and `rollup-gray` does **not**, since rollup excludes dead-end); severity matrix logic present in the renderer (e.g., assert ownSeverity/rollupSeverity branching in the badge-class selection code).
4. **`test_panel_graph_cue_badge_hidden_when_no_cues`** — verifies the renderer guards badge creation behind a non-zero count (e.g., asserts that the badge enter/update is gated on `badgeCount > 0` or an equivalent check).
5. **`test_panel_graph_cue_tooltip_shows_breakdown`** — `showTooltip` body contains the cue section markup (literal text "loop", "revisit", "dead-end") and a per-cue own/inside split. Negative: the section must not render when both counts are zero.

No new test data fixtures needed; the existing trajectory-recording assertions already cover the data sources.

## 7. Risks and trade-offs

- **Visual density**: every URL node may carry a badge once a session is long enough that loops/revisits show up. Mitigation: gray badges fade visually so dead-end-only nodes don't compete with cycle alarms; rollup-only badges (outlined) are visually lighter than own (filled).
- **No `rollup-gray` state**: dead-end is local to the immediate sequence shape, so propagating it via rollup would put gray badges on parent nodes for small bounced branches that may not matter at the parent layer. The chosen trade-off is to suppress dead-end from rollup entirely — the reviewer still sees the dead-end marker on the actual bounced node when they drill in.
- **Only immediate bounce-backs count**: `A -> B -> C -> A` does not mark `B` or `C` as dead-end. This avoids broad false positives from normal exploration paths. If longer backtracking becomes important, add a separate, stricter design for path-level backtrack spans.
- **Stroke conflict at small zoom**: outlined badges may be hard to distinguish from filled at < 0.5x zoom. Acceptable — at that zoom the reviewer is scanning for any badge, not classifying.
- **No new layout**: keeps the existing drill-down semantics. A future change (e.g., unified hierarchy view) can reuse `computeOwnCues` and `attachCueFields` unchanged.
- **Sequence scan cost**: each `buildXxxGraphData` call now walks the sequence arrays once per layer. Trajectories rarely exceed a few hundred events; cost is negligible compared to the existing render pass.

## 8. Out of scope

- Edge-level cycle styling (already exists via `detectCycleEdges` and is not changed).
- Auto-classification of "failure" vs "success" at the trajectory level.
- Cross-session aggregates (cue heatmaps across multiple replays).
- Filtering / sorting the graph by cue severity. The badge is a *visual* attention cue; navigation affordances stay manual.
