# Bounce-Back Dead-End Cues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redefine graph `deadEnd` cues from terminal-node markers to bounce-back branch markers, so `A -> B -> A` marks `B` as the dead-end.

**Architecture:** Keep the existing cue pipeline unchanged: `computeOwnCues(type, node, sequence)` computes own flags, `attachCueFields(...)` attaches those flags to graph nodes, and the existing badge/tooltip renderer displays the result. The only behavior change is inside `computeOwnCues`: dead-end detection becomes an immediate bounce-back sequence check instead of a last-element check.

**Tech Stack:** Vanilla JavaScript in `src/ui/static/graph.js`; pytest contract tests in `tests/test_ui_panel.py`.

**Spec:** `docs/superpowers/specs/2026-05-21-graph-attention-cues-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/ui/static/graph.js` | Modify | Change `computeOwnCues` so `deadEnd` is true when the current node is the middle of `A -> node -> A`, not when it is the final sequence element. |
| `tests/test_ui_panel.py` | Modify | Add a contract test that asserts bounce-back dead-end detection exists and terminal-only detection is gone. |

---

### Task 1: Redefine `deadEnd` as immediate bounce-back

**Files:**
- Modify: `tests/test_ui_panel.py`
- Modify: `src/ui/static/graph.js`
- Test: `tests/test_ui_panel.py`

- [ ] **Step 1: Write the failing test**

Add this test immediately after `test_panel_graph_compute_own_cues_handles_all_three_layers` in `tests/test_ui_panel.py`:

```python
def test_panel_graph_dead_end_uses_bounce_back_not_terminal():
    body = PANEL_HTML.split("function computeOwnCues(type, node, sequence)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # Dead-end means A -> node -> A, so the node is the branch that got backed out of.
    assert "seq[i + 1] === seq[i - 1]" in body
    assert "seq[i] !== seq[i - 1]" in body
    assert "i < seq.length - 1" in body
    # The old terminal-node marker must not set deadEnd anymore.
    assert "seq[seq.length - 1] === node.id" not in body
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_dead_end_uses_bounce_back_not_terminal -v
```

Expected: FAIL because `computeOwnCues` still uses `seq[seq.length - 1] === node.id` and does not check `seq[i + 1] === seq[i - 1]`.

- [ ] **Step 3: Update `computeOwnCues`**

In `src/ui/static/graph.js`, replace the entire existing `computeOwnCues` function with:

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
    if (i > 0 && i < seq.length - 1 && seq[i + 1] === seq[i - 1] && seq[i] !== seq[i - 1]) deadEnd = true;
    if (seen && (i === 0 || seq[i - 1] !== node.id)) revisit = true;
    seen = true;
  }
  const severity = (loop || revisit) ? 'red' : (deadEnd ? 'gray' : 'none');
  return { loop: loop, revisit: revisit, deadEnd: deadEnd, severity: severity };
}
```

`type` remains in the signature for call-site stability and future per-layer branching.

- [ ] **Step 4: Run the targeted test**

```bash
uv run pytest tests/test_ui_panel.py::test_panel_graph_dead_end_uses_bounce_back_not_terminal -v
```

Expected: PASS.

- [ ] **Step 5: Run the existing cue helper tests**

```bash
uv run pytest \
  tests/test_ui_panel.py::test_panel_graph_compute_own_cues_handles_all_three_layers \
  tests/test_ui_panel.py::test_panel_graph_rollup_excludes_dead_end \
  tests/test_ui_panel.py::test_panel_graph_builders_attach_cue_fields \
  tests/test_ui_panel.py::test_panel_graph_tooltip_includes_cue_breakdown \
  -v
```

Expected: PASS. These tests prove the helper shape, rollup exclusion, node field attachment, and tooltip contract still hold.

- [ ] **Step 6: Run all UI panel tests**

```bash
uv run pytest tests/test_ui_panel.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/ui/static/graph.js tests/test_ui_panel.py
git commit -m "Define dead-end cues as bounced branches" -m "Constraint: User confirmed A -> B -> A should mark B, not A, as the dead-end.
Rejected: Terminal-node dead-end | It labels the current final node rather than the backed-out branch.
Rejected: Long-span backtrack detection | It needs a separate design to avoid false positives.
Confidence: high
Scope-risk: narrow
Directive: Keep dead-end excluded from rollup unless parent-level gray semantics are redesigned.
Tested: uv run pytest tests/test_ui_panel.py -q
Not-tested: Full suite may still be blocked by the existing scripts.batch_runner collection issue."
```

---

## Self-Review

**Spec coverage:** The plan implements the spec's updated dead-end definition (`A -> B -> A` marks `B`), preserves existing loop/revisit behavior, preserves dead-end rollup exclusion, and keeps badge/tooltip rendering unchanged.

**Placeholder scan:** No placeholder steps remain. Every edit step includes exact code and every verification step includes the exact command plus expected result.

**Type consistency:** Function and field names match the existing implementation: `computeOwnCues(type, node, sequence)` returns `{ loop, revisit, deadEnd, severity }`; downstream fields remain `ownCues`, `ownSeverity`, `rollupCount`, `rollupSeverity`, `rollupBreakdown`, and `badgeCount`.
