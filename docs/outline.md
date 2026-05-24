# BrowserLens: Interactive Diagnosis of Browser Agent Trajectories via Hierarchical State-Action Graphs

## One-line Thesis

Browser agent의 실행은 화면, DOM, URL, viewport, 입력값, 세션 상태처럼 쉽게 사라지는 browser state에 강하게 의존하지만, 현재의 trajectory artifact는 대부분 선형 로그로 남는다. 본 논문은 browser agent의 **단일 trajectory**를 URL state graph, viewport state graph, state-anchored action graph로 재구성하는 **browser-state-anchored representation**을 제안한다. 이 representation은 reviewer가 loop, repeated state/action, dead end 같은 **graph-structural cue**와 no-op action 같은 **state-change-based outcome cue**를 빠르게 localize하고, screenshot·DOM/ARIA·LLM context evidence를 통해 verify할 수 있게 한다.

> [!note] Core Concept
> BrowserLens reframes browser-agent debugging from reading a chronological action log to inspecting a hierarchical graph of environment-anchored states and actions.

---

## Abstract

Browser agents operate in ephemeral environments where task progress depends on transient browser states such as URL, viewport, DOM, visual layout, input values, and session context. However, most trajectory artifacts are presented as chronological logs, forcing reviewers to manually compare distant steps to identify repeated states, loops, no-op actions, or dead-end behavior.

We introduce **BrowserLens**, an interactive diagnosis system built around a **browser-state-anchored representation**. The representation reconstructs a single browser-agent trajectory into three nested graph layers: a URL state graph, a viewport state graph, and a state-anchored action graph. Each layer defines deterministic node identity rules, edge construction rules, and diagnostic cue predicates. BrowserLens exposes this representation through hierarchical drill-down, layer-wise cue encoding, notification badges for hidden lower-layer cues, and state inspection panels for before/after evidence.

The central contribution is not a graph visualization interface alone, but a representation that anchors browser-agent behavior to environment state identity. This enables reviewers to localize and verify structural diagnostic cues such as revisits, loops, repeated actions, dead ends, and no-op actions in single-run browser-agent trajectories.

---

## Target Users

BrowserLens targets reviewers who need to inspect and explain browser-agent behavior at the trajectory level.

- **Browser agent developer**: A person who debugs failed trajectories to modify agent code, prompts, tool interfaces, or execution policies.
- **Browser agent evaluator**: A researcher, benchmark maintainer, QA engineer, or evaluation analyst who verifies task outcomes and classifies failure behavior without necessarily changing the agent implementation.

### Scope Decision

The initial scope is **read-only diagnosis** for developers and evaluators, not non-developer steering.

Reviewers may observe trajectories during execution or inspect completed trajectories after the run, but they do not intervene in the agent execution. Steering, personalization, graph editing, and self-evolving agent behavior are left as future work. This scope keeps the contribution focused on diagnosing what happened, where it happened, and what evidence supports the diagnosis.

---

## Research Gap

Prior work has advanced browser-agent analysis along three partially overlapping strands, but none directly addresses the need for **single-run, environment-state-anchored, hierarchical diagnosis** of browser-agent trajectories.

| Strand | Representative work | Contribution | Remaining gap |
| :--- | :--- | :--- | :--- |
| **A. Agent debugging and layered diagnosis** | DiLLS, AgentLens, AgDebugger, AgentTrace, AgentDiagnose, Agent Trajectory Explorer | These systems reduce linear-log overload by organizing agent traces into hierarchical or causal structures such as Activity / Action / Operation or root-cause graphs. | They primarily focus on agent intent, operation structure, or multi-agent collaboration. Browser-specific environment state identity—URL, viewport, DOM, and visible region—is not treated as the primary diagnostic axis. |
| **B. Browser/web agent benchmarks and trajectory logging** | Mind2Web, WebArena, WebVoyager, illusion-progress, REAL, WebWalker, BEARCUBS, Mind2Web 2; AgentBoard, WebGraphEval | These benchmarks and evaluation tools record browser-agent trajectories with screenshots, DOM snapshots, actions, and task-level success/failure labels. Some aggregate behavior across multiple runs. | They provide rich logging and scoring, but usually present a single trajectory as a chronological trace. They do not reconstruct a single run into environment-state identity graphs that reveal revisits, loops, repeated actions, or no-op outcomes. |
| **C. Graph-based behavior visualization and process mining** | QLens, GNNLens, trajectory flow maps, event knowledge graphs, process mining workflow graphs, human web navigation graphs | These systems show that sequential behavior can be modeled as graphs to surface loops, revisits, deviations, and topological motifs. | They are not specialized for browser-agent single-run diagnosis. They do not combine URL identity, viewport identity, state-anchored action identity, and hierarchical drill-down into one reviewer-facing diagnostic representation. |

The gap is therefore not simply that “browser trajectories have not been visualized as graphs.” The narrower gap is:

> Existing tools do not provide a **single-run browser-agent diagnosis representation** that anchors agent behavior to browser environment state identity across URL, viewport, and action layers, while exposing structural and outcome cues that reviewers can localize and verify with evidence.

BrowserLens addresses this gap by combining three ingredients:

1. **Agent-trajectory diagnosis**: the goal is to inspect and explain a single browser-agent run.
2. **Browser environment anchoring**: states are identified through URL, viewport, DOM/ARIA, visual, and action-context evidence.
3. **Hierarchical graph drill-down**: the trajectory is reconstructed into URL, viewport, and state-anchored action graphs.

---

## Problem Statement

Browser agents differ from code agents in that their execution does not primarily leave behind durable artifacts such as files, commits, or test outputs. Instead, task progress is often encoded in ephemeral browser states: the current page, scroll position, visible DOM region, modal state, form values, session state, and transient UI feedback.

As a result, browser-agent diagnosis cannot rely only on the agent-intent axis, such as what the agent planned or which tool call it made. It must also expose the **environment-state axis**, namely where the agent was, what part of the page it saw, and whether its actions changed the browser state.

This creates two diagnosis gaps.

### Gap 1 — Env-axis Gap

Existing agent diagnosis tools can often answer:
- What was the agent trying to do?
- Which action or operation did it execute?
- Which reasoning step preceded the tool call?

However, browser-agent reviewers also need to answer:
- Which page was the agent on at this step?
- Which viewport or DOM region was visible?
- Did the agent return to a page or region it had already visited?
- Did the action alter the browser state?

Without an explicit environment-state axis, failures such as wrong-page navigation, page identification errors, in-page search failure, modal trapping, or repeated interaction with the same UI region are difficult to diagnose.

### Gap 2 — Linear-trace Gap

Even when screenshots, DOM snapshots, URLs, and actions are logged at every step, a linear trace makes structural failure patterns hard to see. Browser-specific failures often emerge across non-adjacent steps:
- returning to the same URL after several transitions,
- repeatedly scrolling through the same region,
- repeatedly clicking the same target,
- cycling between two pages or viewports,
- terminating after multiple no-op interactions.

In a sequence or tree trace, the same browser state appears as separate step instances. The reviewer must manually compare URLs, screenshots, DOM snippets, scroll positions, and action targets across distant steps. This increases diagnosis time and makes reviewer judgments inconsistent.

---

## Design Goals

BrowserLens converts a browser-agent trajectory from a chronological execution record into a **diagnosable structural artifact**. The design goals map directly to the two gaps.

### DG1. Environment-state diagnosis
Reviewers should be able to answer environment-state questions at any point in the trajectory:
- Which URL/page was the agent on?
- Which viewport or DOM region was visible?
- Which actions were performed in that state?
- What evidence supports that interpretation?

This goal addresses the env-axis gap.

### DG2. Structural-failure visibility
Reviewers should be able to see diagnostic cues that are difficult to detect in a linear trace:
- repeated URL or viewport states,
- URL-level and viewport-level loops,
- repeated state-anchored actions,
- local action loops,
- terminal dead ends,
- no-op actions where the browser state did not meaningfully change.

These cues are not automatic failure labels. They are **attention cues** that reviewers verify using evidence. This goal addresses the linear-trace gap.

---

## Terminology

To avoid overclaiming, BrowserLens distinguishes cue generation from failure classification.

| Term                 | Definition                                                                                                                                                           |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Diagnostic cue**   | Umbrella term for a pattern surfaced to attract reviewer attention. A cue may or may not correspond to an actual failure.                                            |
| **Structural cue**   | A diagnostic cue derived from graph topology, node frequency, edge traversal, or terminal graph position. Examples: repeated state, loop, repeated action, dead end. |
| **Outcome cue**      | A diagnostic cue derived from the relationship between pre-action and post-action browser states. Example: no-op action.                                             |
| **Verified failure** | A reviewer-confirmed failure explanation supported by trajectory evidence.                                                                                           |
| **Evidence**         | Step references, screenshot pairs, DOM/ARIA snippets, URL/viewport state, tool calls, LLM context, or before/after diffs used to verify or reject a cue.             |

---

## Framework: Browser-state-anchored Representation

The core contribution is a **browser-state-anchored representation** for single-run browser-agent diagnosis. BrowserLens is an interactive instantiation of this representation.

The representation takes a browser-agent trajectory as input and constructs a **hierarchical state-action graph** with three layers:
1. URL state graph,
2. viewport state graph,
3. state-anchored action graph.

The two design goals map to the framework as follows:
- **DG1** is addressed by defining URL, viewport, and action-context layers that make environment state inspectable.
- **DG2** is addressed by defining structural and outcome cue predicates on top of the graph representation.

---

## F0. Trajectory Input Schema

The input is a time-ordered browser-agent trajectory:

$$T = [(s_1, a_1, s_2), (s_2, a_2, s_3), \dots, (s_n, a_n, s_{n+1})]$$

Each transition consists of a pre-action browser state, an agent action, and a post-action browser state.

### Browser state

$$s_t = (\text{url}_t, \text{viewport}_t, \text{DOM}_t, \text{screenshot}_t, \text{meta}_t)$$

| Field | Meaning |
| :--- | :--- |
| `url_t` | Observed URL at step `t`. |
| `viewport_t` | Scroll position, viewport bounds, visible region descriptor, and related viewport metadata. |
| `DOM_t` | DOM/ARIA snapshot or accessibility tree. |
| `screenshot_t` | Screenshot or visual evidence. |
| `meta_t` | Timestamp, tab id, session id, browser context id, and auxiliary metadata. |

### Agent action

$$a_t = (\text{type}_t, \text{target}_t, \text{value}_t, \text{tool-call}_t, \text{LLM-context}_t)$$

| Field | Meaning |
| :--- | :--- |
| `type_t` | Atomic browser action type such as click, type, scroll, select, hover, wait, or navigate. |
| `target_t` | Action target represented by selector, DOM/ARIA node, coordinate, role, accessible name, or visual target. |
| `value_t` | Input value, selected option, scroll direction, or other action-specific value. |
| `tool-call_t` | Browser tool call name and arguments. |
| `LLM-context_t` | LLM input context, raw response, and optional reasoning trace if available. |

### Trajectory metadata

$$M = (\text{task}_\text{goal}, \text{task}_\text{success}, \text{terminal}_\text{step})$$

Metadata includes the task goal, success/failure label, and terminal step.

---

## F1. Hierarchical State-Action Graph

BrowserLens constructs three directed graph layers:

$$G_\text{url} = (V_\text{url}, E_\text{url}), \quad G_\text{viewport} = (V_\text{viewport}, E_\text{viewport}), \quad G_\text{action} = (V_\text{action}, E_\text{action})$$

Each layer has two construction rules.

| Rule | Definition |
| :--- | :--- |
| **Node identity rule** | Maps raw trajectory instances into deterministic node identifiers. Instances with the same identifier are merged into one graph node. |
| **Edge construction rule** | Converts temporal adjacency in the trajectory into directed transitions between layer-specific nodes. |

The layer-specific node sets are:

```text
V_url      = { id_url(s_t) | s_t appears in T }
V_viewport = { id_viewport(s_t) | s_t appears in T }
V_action   = { id_action(a_t; s_t) | (s_t, a_t, s_{t+1}) appears in T }
```

Merged nodes accumulate diagnostic attributes such as:

```text
count
step_refs
evidence_refs
incoming_edges
outgoing_edges
first_seen
last_seen
```

The key design decision is that each layer uses different node semantics:

```text
id_url(s_t)          → URL state node
id_viewport(s_t)     → viewport state node
id_action(a_t; s_t)  → state-anchored action node
```

The URL and viewport layers show **where the agent was**. The action layer shows **what the agent repeatedly did there**.

---

## Design Alternatives Considered

BrowserLens uses a URL → viewport → action hierarchy because it matches the structure of browser-agent behavior while remaining inspectable. Several alternatives were considered.

| Alternative                                              | Benefit                                                  | Limitation                                                                                               | BrowserLens decision                                                                                     |
| :------------------------------------------------------- | :------------------------------------------------------- | :------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------- |
| **Single flat state-action graph**                       | Preserves all transitions in one graph.                  | Quickly becomes dense and difficult to interpret for long trajectories.                                  | Use hierarchical layers to support overview-to-detail diagnosis.                                         |
| **Task-intent hierarchy**                                | Captures agent plans, subgoals, and reasoning structure. | Does not directly answer environment-state questions such as which page or viewport the agent revisited. | Treat task intent and LLM context as evidence, not as the primary graph axis.                            |
| **DOM-state graph**                                      | Represents fine-grained browser state changes.           | Dynamic DOM, ads, timestamps, lazy loading, and selector instability can fragment equivalent states.     | Use viewport-level identity as the middle layer; retain DOM/ARIA as evidence and for outcome cues.       |
| **State-as-node / action-as-edge action layer**          | Represents no-op actions as self-loops naturally.        | Dense local routines become harder to read because repeated action labels are distributed across edges.  | Use action-as-node rendering for local behavioral diagnosis; verify no-op through before/after evidence. |
| **Cross-run aggregate behavior graph**                   | Useful for benchmark-level behavior analysis.            | Obscures the exact evidence chain of a single failed run.                                                | Focus on single-run diagnosis; aggregate analysis is future work.                                        |
| **Similarity-based matching as the core representation** | More robust to noisy DOM and visual changes.             | Adds model-dependent assumptions and complicates interpretation.                                         | Use deterministic identity in the core representation; leave similarity-aware matching as an extension.  |

This choice keeps the representation interpretable while aligning with how browser tasks unfold: agents navigate across pages, inspect regions within a page, and perform local UI actions.

---

## Layer 1 — URL State Graph

The **URL state graph** represents page-level browser states visited during the trajectory.

### Node identity rule

```text
id_url(s_t) = canonicalize(url_t)
```

The prototype uses canonicalized URLs. Canonicalization may preserve or discard query parameters depending on task context. For example:
- search-result pages may require query parameters to distinguish task-relevant states;
- login or checkout flows may require redirect targets or page titles;
- route patterns may be needed for dynamic web applications.

The core representation does not prescribe one universal canonicalization policy. It requires the policy to be explicit and deterministic.

### Edge construction rule

```text
E_url = {
  (id_url(s_t), id_url(s_{t+1}))
  | (s_t, a_t, s_{t+1}) ∈ T
    ∧ id_url(s_t) ≠ id_url(s_{t+1})
}
```

A URL edge represents a page-level transition caused by link clicks, redirects, form submissions, browser back/forward actions, or direct navigation. Interactions that do not change the URL are handled by lower layers.

### Node attributes

| Attribute | Meaning |
| :--- | :--- |
| `visit_count` | Number of state instances merged into this URL node. |
| `step_refs` | Trajectory steps associated with this URL. |
| `first_seen`, `last_seen` | First and last trajectory step where this URL appears. |
| `incoming_edges`, `outgoing_edges` | Page-level transition relations. |
| `evidence_refs` | Representative screenshots, DOM/ARIA snapshots, and action references. |

### Diagnostic value

The URL layer exposes page-level movement patterns:
- wrong-page navigation,
- navigation drift,
- repeated page visits,
- page-level loops,
- terminal failure on an irrelevant page.

In a linear trace, repeated visits to the same page are scattered across step indices. In the URL graph, they are merged into a single inspectable state node.

---

## Layer 2 — Viewport State Graph

The **viewport state graph** represents visible page regions within a URL state. Expanding a URL node reveals the viewport sub-graph for that page.

### Node identity rule

```text
id_viewport(s_t) =
(
  id_url(s_t),
  canonicalize_viewport(viewport_t)
)
```

Viewport identity is URL-scoped. The same scroll position or visible DOM pattern on two different URLs should not be merged.

`canonicalize_viewport(viewport_t)` can use:
- scroll-position buckets,
- viewport bounds,
- visible DOM landmark sequences,
- visible heading/ARIA landmarks,
- modal or panel visibility state,
- representative screenshot fingerprint metadata.

The prototype uses deterministic viewport descriptors such as scroll bucket, viewport bounds, and visible DOM landmark sequence.

### Edge construction rule

```text
E_viewport = {
  (id_viewport(s_t), id_viewport(s_{t+1}))
  | (s_t, a_t, s_{t+1}) ∈ T
    ∧ id_url(s_t) = id_url(s_{t+1})
    ∧ id_viewport(s_t) ≠ id_viewport(s_{t+1})
}
```

A viewport edge represents within-page movement or visible-region changes, such as:
- scroll,
- anchor jump,
- accordion expansion,
- modal open/close,
- in-page navigation,
- visible DOM region shift.

URL-changing transitions are represented in the URL layer and not duplicated as viewport edges.

### Node attributes

| Attribute | Meaning |
| :--- | :--- |
| `visit_count` | Number of trajectory states mapped to the viewport node. |
| `step_refs` | Step references for this viewport. |
| `parent_url_id` | Parent URL node. |
| `scroll_range` | Scroll bucket or merged scroll range. |
| `visible_landmarks` | Representative visible DOM/ARIA landmarks. |
| `representative_screenshot` | Screenshot evidence for the viewport. |
| `incoming_edges`, `outgoing_edges` | Within-page transition relations. |

### Diagnostic value

The viewport layer exposes within-page exploration failures:
- repeated scrolling through the same region,
- failure to reach the target section,
- getting trapped in a modal or panel,
- repeated inspection of irrelevant content,
- in-page search failure.

This layer captures behavior that the URL layer cannot distinguish because the page URL remains unchanged.

---

## Layer 3 — State-Anchored Action Graph

The **state-anchored action graph** represents local browser actions performed inside a specific viewport context.

Unlike the URL and viewport layers, whose nodes are environment states, the action layer uses **action equivalence classes as nodes**. Each action node is anchored to the pre-action browser context.

### Node identity rule

```text
id_action(a_t; s_t) =
(
  id_viewport(s_t),
  action_type_t,
  canonicalize_action_args(a_t)
)
```

The parent viewport is part of the action identity. Clicking a “Search” button in different URL or viewport states produces different action nodes.

```text
canonicalize_action_args(a_t) =
(
  action_type_t,
  target_fingerprint_t,
  normalized_input_value_t?
)
```

### Action identity policy

| Action type | Identity policy | Rationale |
| :--- | :--- | :--- |
| `click` | Target-sensitive, value-insensitive. | Repeated clicks on the same target should merge into one repeated-action cue. |
| `scroll` | Direction- or target-sensitive. | Repeated scrolling patterns should be interpretable with viewport transitions. |
| `type` | Target- and value-sensitive. | Typing different values into the same field may represent diagnostically distinct attempts. |
| `select` | Target- and value-sensitive. | Choosing different options should remain distinguishable. |
| `hover` | Target-sensitive. | Hover behavior is usually meaningful at the target level. |
| `wait` | Context-sensitive. | Waiting in the same viewport can indicate load uncertainty or stalled progress. |
| `navigate` | Destination-sensitive. | Direct navigation should preserve the target URL or route intent. |

### Edge construction rule

```text
E_action = {
  (id_action(a_t; s_t), id_action(a_{t+1}; s_{t+1}))
  | (s_t, a_t, s_{t+1}), (s_{t+1}, a_{t+1}, s_{t+2}) ∈ T
    ∧ id_viewport(s_t) = id_viewport(s_{t+1})
}
```

Action edges represent consecutive local actions within the same parent viewport. If an action changes URL or viewport, that transition is represented in the upper layer.

The implementation may show cross-viewport action boundaries as dotted connectors or boundary markers for orientation, but the core representation keeps action graphs local to their parent viewport. This separation prevents the action graph from duplicating URL and viewport transitions.

### Node attributes

| Attribute | Meaning |
| :--- | :--- |
| `action_type` | click, type, scroll, select, hover, wait, navigate, etc. |
| `target_fingerprint` | DOM/ARIA, text, role, coordinate, selector, or accessible-name fingerprint. |
| `function_call` | Executed browser tool call. |
| `function_args` | Tool call arguments. |
| `observed_url` | URL at the action step. |
| `parent_viewport_id` | Viewport context where the action occurred. |
| `pre_state_refs` | Browser state references before the action. |
| `post_state_refs` | Browser state references after the action. |
| `dom_aria_state` | DOM/ARIA evidence at the action step. |
| `screenshot_pair` | Before/after screenshots. |
| `llm_context_response` | LLM input context and raw response. |
| `reasoning` | Agent reasoning if available. |
| `summary` | Reviewer-facing one-line action summary. |
| `outcome` | Action outcome summary. |
| `action_steps` | Step references merged into the action node. |
| `count` | Number of executions of this action identity. |

### Diagnostic value

The action layer exposes local behavioral routines:
- repeated clicking,
- repeated typing,
- filter manipulation loops,
- invalid interaction with the same target,
- repeated wait or scroll behavior,
- action sequences that cycle without progress.

Because action nodes preserve pre/post state evidence, reviewers can verify whether repeated actions were benign exploration, necessary correction, or true failure behavior.

---

## Internal Model vs. UI Rendering

Internally, BrowserLens stores canonical transitions as state-action-state triples:

```text
s_t --a_t--> s_{t+1}
```

The action layer is rendered as an action-centric graph:

```text
a_t --> a_{t+1}
```

This rendering is chosen because the fine-grained diagnosis question is often:
> What did the agent repeatedly do in this browser context?

A state-as-node/action-as-edge rendering would make no-op actions appear as self-loops more directly, but it can make dense local action routines harder to read. BrowserLens therefore renders repeated action routines as action nodes while preserving pre/post state evidence for no-op verification.

---

## F2. Diagnostic Cue Definitions

BrowserLens surfaces **diagnostic cues**, not automatic failure labels.

Each cue has the following schema:

```text
DiagnosticCue =
(
  layer,
  type,
  scope,
  predicate,
  severity,
  confidence,
  evidence_refs
)
```

| Field | Meaning |
| :--- | :--- |
| `layer` | `url`, `viewport`, `action`, or `detail`. |
| `type` | repeated state, state loop, repeated action, action loop, state dead end, no-op action, terminal no-op, etc. |
| `scope` | Node, edge, path, subgraph, action instance, or before/after state pair. |
| `predicate` | Rule used to surface the cue. |
| `severity` | Cue strength derived from count, cycle length, traversal frequency, terminality, or lack of state progress. |
| `confidence` | Reliability of the cue under the available evidence and identity policy. |
| `evidence_refs` | Step, screenshot, DOM/ARIA, LLM context, and before/after state references. |

A cue is surfaced when its predicate is true. Whether it is a real failure is determined by reviewer verification.

---

## F2.1 Meaningful State Change

Several cues depend on whether a browser action meaningfully changed the environment. BrowserLens defines a helper predicate:

```text
meaningful_state_change(s_t, s_{t+1}) =
  url_changed
  ∨ viewport_changed
  ∨ meaningful_dom_changed
  ∨ meaningful_visual_changed
  ∨ input_value_changed
  ∨ modal_or_panel_state_changed
```

Where:

```text
url_changed =
  id_url(s_t) ≠ id_url(s_{t+1})

viewport_changed =
  id_viewport(s_t) ≠ id_viewport(s_{t+1})

meaningful_dom_changed =
  filtered_dom_diff(DOM_t, DOM_{t+1}) ≠ ∅
```

`filtered_dom_diff` ignores cosmetic or known-noisy changes such as timestamps, animation-only mutations, ads, telemetry attributes, transient focus outlines, and irrelevant script-generated identifiers when the logging format supports such filtering.

The prototype reports both raw diff and filtered diff when available. This prevents no-op detection from depending on a brittle exact DOM equality check.

---

## F2.2 State-level Structural Cues

State-level cues are defined on URL and viewport graphs.

### Repeated State Cue

```text
count(StateNode) ≥ k_state
```

Prototype default:
```text
k_state = 2
```

A repeated state cue indicates that the agent returned to the same URL or viewport identity. The cue severity increases with:
- visit count,
- temporal distance between visits,
- repeated traversal of the same incoming/outgoing edges,
- task failure terminality,
- absence of meaningful progress between visits.

This cue may indicate navigation drift, in-page search failure, or wrong-page revisits, but it can also represent legitimate exploration.

### State Loop Cue

A state loop exists when the graph contains a directed cycle:

```text
S_1 → S_2 → ... → S_k → S_1
```

Additional attributes:
```text
cycle_length
traversal_count
step_span
cycle_closing_edge
```

A state loop cue indicates recurring page-level or viewport-level movement. BrowserLens highlights the edge that closes the cycle and provides the corresponding step references.

### State Dead End Cue

A state dead end is a terminal failed state with no recent meaningful progress.

```text
is_terminal_state = true
∧ task_success = false
∧ no meaningful_state_change in the last m actions
```

Prototype default:
```text
m = 3
```

This avoids labeling every failed final state as a dead end. A failed terminal state becomes a dead-end cue only when the recent action window shows no meaningful browser-state progress.

---

## F2.3 Action-level Structural Cues

Action-level structural cues are defined on the state-anchored action graph.

### Repeated Action Cue

```text
count(ActionNode) ≥ k_action
```

Prototype default:
```text
k_action = 2
```

A repeated action cue indicates that the same state-anchored action identity occurred multiple times. Examples include:
- repeated click on the same button,
- repeated typing of the same value into the same field,
- repeated selection of the same option,
- repeated scroll or wait behavior in the same viewport.

Severity increases with execution count, terminal proximity, and lack of meaningful state change after the action instances.

### Action Loop Cue

An action loop exists when the local action graph contains a directed cycle:

```text
A_1 → A_2 → ... → A_k → A_1
```

Additional attributes:
```text
cycle_length
traversal_count
parent_viewport_id
step_refs
```

This cue can reveal repeated local routines, such as:
- open filter → select option → close filter → open filter,
- type query → click search → clear field → type query,
- scroll down → scroll up → scroll down.

---

## F2.4 Outcome Cues

Outcome cues are based on pre-action and post-action state comparison.

### No-op Action Cue

A no-op action occurs when an action is executed but the browser state does not meaningfully change.

```text
no_op_action(a_t) =
  ¬ meaningful_state_change(s_t, s_{t+1})
```

The detail panel shows:
- before/after screenshots,
- visual diff if available,
- DOM/ARIA diff,
- URL and viewport comparison,
- input-value comparison,
- tool call and output,
- LLM context.

No-op is not treated as a primary graph-topological motif. It is an outcome cue verified through evidence.

### Terminal No-op Cue

A terminal no-op is a failed trajectory whose final intervention produced no meaningful state change.

```text
is_terminal_action = true
∧ task_success = false
∧ no_op_action(a_t) = true
```

This cue is a subtype of no-op action, not an independent graph motif. It is shown through the action detail panel and terminal markers.

---

## F3. Trajectory Ingestion

The representation supports two ingestion modes.

### Live streaming mode

During agent execution, BrowserLens incrementally ingests each transition:

```text
(s_t, a_t, s_{t+1})
```

The graph is updated online as new nodes, edges, and cue predicates become available. Reviewers can observe the graph build up during execution.

### Post-hoc import mode

For completed trajectories, BrowserLens imports the full trajectory and constructs the graph in one pass.

Both modes apply the same deterministic node identity and edge construction rules. Therefore, the resulting graph should be equivalent, except for intermediate states visible during live streaming.

### Adapter boundary

The initial prototype assumes a specific browser-agent logging format. Applying BrowserLens to other frameworks requires adapters that map framework-specific logs into the F0 schema.

---

## System: BrowserLens

BrowserLens is an interactive system that exposes the hierarchical state-action graph to reviewers. The system provides two main capabilities:
1. hierarchical drill-down across URL, viewport, and action layers;
2. layer-wise cue encoding and notification badges.

Session replay and action detail panels are supporting components that provide evidence for verification.

---

## S1. Hierarchical Drill-down

Reviewers start from the URL-level overview. They can expand a URL node to inspect its viewport graph, then expand a viewport node to inspect its local state-anchored action graph.

```text
URL graph
  └── Viewport graph for selected URL
        └── Action graph for selected viewport
```

The interaction supports:
- expand/collapse of URL and viewport nodes,
- synchronized step selection across graph, replay, and detail panel,
- overview-to-detail navigation,
- return to parent graph without losing selected evidence.

This drill-down maps the representation directly to reviewer workflow:
1. identify page-level movement,
2. inspect within-page exploration,
3. inspect local action routines and outcomes.

---

## S2. Cue Encoding and Notification Badges

BrowserLens separates cues that can be read directly from the current graph layer from cues hidden inside collapsed lower layers.

### Primary visual encoding

Primary encoding shows cues that are directly observable in the current layer.

| Cue | Primary encoding | Rationale |
| :--- | :--- | :--- |
| **Repeated state** | URL/viewport node size and color intensity | Visit count is a node attribute in the current state layer. |
| **Repeated action** | Action node size and color intensity | Execution count is a node attribute in the action layer. |
| **State loop / action loop** | Highlighted cycle-closing edge | The cue is defined by transition structure rather than by a single node. |
| **State dead end** | Terminal node outline or stroke | The cue combines terminal failure with lack of recent meaningful progress. |
| **No-op action** | Detail panel before/after diff and status chip | The cue depends on state comparison, not graph topology. |
| **Terminal no-op** | Detail panel terminal marker and status chip | This is a terminal subtype of no-op action. |

### Node encoding

| Encoding channel | Meaning |
| :--- | :--- |
| Color intensity | Node frequency: visit count for state layers, execution count for action layer. |
| Size | Node frequency. |
| Shape | Start node, terminal node, and ordinary node type. |
| Stroke / outline | Dead-end candidate or terminal failure state. |
| Badge | Hidden lower-layer cue summary only. |

### Edge encoding

| Encoding channel | Meaning |
| :--- | :--- |
| Direction | Temporal transition order. |
| Width | Number of traversals between the same node pair. |
| Highlight | Cycle-closing edge or selected path. |
| Dotted boundary edge | Optional implementation marker for cross-layer or cross-viewport action boundaries. |

### Notification badge principle

Badges summarize only cues hidden inside collapsed lower layers.

> [!important] Badge Principle
> A cue already visible in the current graph layer is not duplicated in the badge. A badge only summarizes lower-layer cues hidden by collapse.

Examples:

```text
Collapsed URL node badge: [5]
Breakdown:
- Viewport loop: 1
- Action loop: 1
- Repeated action: 2
- No-op action: 1
```

```text
Collapsed viewport node badge: [3]
Breakdown:
- Repeated action: 2
- No-op action: 1
```

Thus, URL repeated state is shown by the URL node’s size and color, not by a badge. The badge is reserved for hidden viewport/action cues.

---

## S3. Supporting Components

### Session Replay

Session Replay lets reviewers move through the trajectory step by step.

It provides:
- play / pause / seekbar interaction,
- synchronized screenshot,
- current URL,
- current viewport,
- action metadata,
- selected graph node or edge highlight.

This component is included as scaffolding because reviewers need temporal evidence to verify graph cues.

### Action Detail Panel

The Action Detail Panel shows evidence for selected action nodes and action instances.

It includes:
- before/after screenshots,
- screenshot diff if available,
- DOM/ARIA diff,
- URL and viewport comparison,
- input value comparison,
- tool call and output,
- LLM context and raw response,
- action outcome summary,
- cue status chips.

No-op action cues and terminal no-op cues are verified here rather than through primary graph encoding.

---

## Design Rationale

| Contribution | Source analogy | Why it transfers | Browser-agent adaptation |
| :--- | :--- | :--- | :--- |
| **F1. Hierarchical State-Action Graph** | Layered agent debugging, distributed tracing, hierarchical behavior abstraction | Hierarchy lets reviewers select the level of detail needed for diagnosis. | BrowserLens shifts the primary hierarchy from agent intent to browser environment state: URL, viewport, and state-anchored action. |
| **F2. Diagnostic Cue Definitions** | Control-flow graph cycle detection, process mining, event-log analysis, before/after diff inspection | Loops, revisits, repeated behavior, and no-progress outcomes are hard to detect in linear logs but visible as structural or outcome cues. | BrowserLens defines layer-specific identity rules and treats cues as reviewer-verifiable evidence prompts rather than automatic failure labels. |
| **S1. Drill-down UI** | File explorers, flame graphs, trace-span-event inspection | Collapse/expand supports movement between overview and detail. | URL and viewport provide browser-specific spatial hierarchy; action graphs provide local behavioral detail. |
| **S2. Cue Encoding and Badges** | Workflow viewers, graph motif visualization, debugger status panels | Visual encoding directs attention while preserving reviewer judgment. | BrowserLens uses node frequency, cycle-closing edge highlights, terminal outlines, and lower-layer badges; no-op is verified through evidence panels. |

---

## Contributions

### C1. Problem framing
We characterize browser-agent diagnosis as an environment-state diagnosis problem. Browser-agent failures are difficult to inspect because task progress is tied to ephemeral browser states such as URL, viewport, DOM, screenshot, input values, and session state. This yields two gaps:
- the **env-axis gap**, where agent-intent traces do not answer browser-state questions;
- the **linear-trace gap**, where revisits, loops, repeated actions, and no-op outcomes are hidden across distant steps.

### C2. Browser-state-anchored representation
We introduce a representation that reconstructs a single browser-agent trajectory into:
- a URL state graph,
- a viewport state graph,
- a state-anchored action graph.

Each layer defines deterministic node identity rules, edge construction rules, node attributes, and diagnostic cue predicates. The representation surfaces structural cues and outcome cues that reviewers can verify with evidence.

### C3. BrowserLens system
We instantiate the representation in BrowserLens, an interactive diagnosis system with:
- hierarchical drill-down across URL, viewport, and action layers;
- layer-wise cue encoding;
- notification badges for hidden lower-layer cues;
- synchronized session replay and action detail evidence panels.

### C4. Evaluation design
We propose a within-subjects user study comparing BrowserLens against fair linear baselines. The study measures whether the representation improves cue localization, verification accuracy, sensemaking workflow, and evidence-grounded failure explanation.

---

## Research Questions

### RQ1 — Localization and verification effectiveness
Does BrowserLens help reviewers localize and verify structural and outcome cues faster and more accurately than a linear trajectory viewer?

### RQ2 — Hierarchical sensemaking process
How do reviewers use the URL → viewport → action hierarchy to construct an explanation of a browser-agent trajectory?

### RQ3 — Cue-evidence reasoning
How do reviewers combine graph-structural cues with state evidence to distinguish true failures from benign repetition or intentional exploration?

---

## Evaluation Plan

### Study Design
The study uses a within-subjects design. Each participant inspects browser-agent trajectories under multiple interface conditions. Task order, trajectory order, and condition order are counterbalanced.

### Participants
Participants are recruited from groups likely to perform browser-agent diagnosis:
- browser-agent developers,
- web automation engineers,
- QA engineer,
- HCI/system researchers,
- benchmark or evaluation maintainers.

### Conditions
To reduce confounds, BrowserLens is compared against linear baselines with carefully controlled evidence access.

| Condition                     | Description                                                                           | Purpose                                                                    |
| :---------------------------- | :------------------------------------------------------------------------------------ | :------------------------------------------------------------------------- |
| **C1. Linear log only**       | Chronological trajectory viewer with screenshot, URL, action, and replay.             | Ecological baseline approximating common browser-agent trajectory viewers. |
| **C2. Linear log + evidence** | Same linear viewer, but with DOM/ARIA, LLM context, and before/after diff inspection. | Fair baseline that controls for evidence access.                           |
| **C3. BrowserLens**           | Hierarchical graph representation with the same evidence access as C2.                | Tests the added value of graph-based environment-state representation.     |

The primary effectiveness comparison is **C2 vs. C3**, because both provide the same evidence types. C1 is used to contextualize ecological benefit relative to common linear viewers.

### Tasks
Participants inspect successful and failed browser-agent trajectories. For each trajectory, they produce four operation-level outputs.

| Task output           | Description                                                                                                                                          | Scoring                                                                          |
| :-------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------- |
| **Cue localization**  | Mark the trajectory segment involved in the failure or diagnostic cue, including start/end step and relevant URL/viewport/action node if applicable. | Overlap with ground-truth segment using IoU or step-level precision/recall.      |
| **Cue type**          | Classify the cue as repeated state, state loop, repeated action, action loop, state dead end, no-op action, terminal no-op, or benign behavior.      | Classification accuracy against expert annotation.                               |
| **Cause explanation** | Write a 1–3 sentence explanation of the likely cause.                                                                                                | Expert-coded rubric: causal specificity, evidence-groundedness, and correctness. |
| **Evidence used**     | Identify evidence used: node/path, screenshot diff, DOM/ARIA snippet, URL/viewport comparison, tool call, or LLM context.                            | Checklist score and evidence frequency count.                                    |

### Ground Truth
Each trajectory is independently annotated by two expert annotators.

Ground truth includes:
- relevant step span,
- cue type,
- involved URL/viewport/action nodes,
- whether the cue is a verified failure or benign behavior,
- expected evidence,
- likely root cause.

Disagreements are resolved through discussion. Inter-rater agreement is reported using appropriate measures such as Cohen’s $\kappa$ for categorical labels and overlap statistics for segment annotations.

### Measures

#### RQ1 measures
- time-to-first-correct-localization,
- localization IoU,
- step-level precision and recall,
- cue-type classification accuracy,
- false positive rate,
- verification accuracy,
- participant confidence rating.

#### RQ2 measures
- drill-down sequence,
- expand/collapse history,
- selected node/path history,
- transition patterns between URL, viewport, action, replay, and detail panel,
- think-aloud coding.

#### RQ3 measures
- evidence-used checklist,
- frequency of screenshot diff, DOM/ARIA, URL/viewport, and LLM-context use,
- explanation quality score,
- cases where participants reject a cue as benign,
- post-task interview coding.

### Analysis
The analysis focuses on both performance and process.
- For RQ1, compare conditions using repeated-measures statistical tests or mixed-effects models, depending on sample size and trajectory balance.
- For RQ2, analyze interaction logs and think-aloud data to identify coarse-to-fine, evidence-first, and replay-first strategies.
- For RQ3, code explanations and evidence-use patterns to determine how reviewers verify or reject cues.

---

## Hypotheses

### H1 — Effectiveness
Reviewers using BrowserLens will localize and verify diagnostic cues more accurately and faster than reviewers using the fair linear evidence baseline.

### H2 — Hierarchical sensemaking
Reviewers will often use a coarse-to-fine strategy: first identifying suspicious URL-level or viewport-level structure, then drilling down into action nodes and evidence panels.

### H3 — Cue-evidence integration
Graph cues will help reviewers decide where to inspect, while state evidence will help them determine whether a cue is a true failure or benign repetition.

---

## Limitations

### Diagnosis only
BrowserLens focuses on finding and explaining where trajectory behavior failed. It does not directly recommend prompt changes, code fixes, recovery policies, or agent redesigns.

### Framework-specific trajectory adapters
The prototype assumes a browser-agent logging format that includes URL, viewport, DOM/ARIA, screenshot, action metadata, and LLM context. Other frameworks require adapters to map their logs into the F0 schema.

### Deterministic identity
The core representation uses deterministic URL, viewport, and action identity rules. This keeps the graph interpretable, but dynamic content, sticky headers, lazy loading, A/B variants, selector instability, and visual layout shifts can split equivalent states into multiple nodes.

### Cue false positives
Repeated actions, loops, revisits, and no-op outcomes are not always failures. They can reflect valid exploration, comparison, confirmation, or recovery behavior. BrowserLens therefore treats them as diagnostic cues to verify, not automatic failure labels.

### Predicate sensitivity
Prototype predicates use thresholds such as $k_\text{state} = 2$, $k_\text{action} = 2$, and $m = 3$. These thresholds may need tuning for different task domains, trajectory lengths, and logging granularities.

### Browser-agent scope
BrowserLens focuses on browser-state diagnosis. Multi-agent delegation, MCP calls, external API calls, code execution, and complex non-browser tool orchestration are outside the initial scope unless they are logged as evidence linked to browser actions.

### Study scope
The proposed evaluation can compare BrowserLens against fair linear baselines, but it may not fully isolate every UI feature. Further ablations could separately test graph hierarchy, cue encoding, notification badges, and detail-panel evidence.

### Reviewer population
The target population is developers and evaluators. Findings may not generalize to non-technical end users who want steering, personalization, or direct intervention during agent execution.

---

## Future Work

### Similarity-based robust matching
Future versions can extend deterministic identity with similarity-aware matching:
- visual hashing,
- DOM landmark Jaccard similarity,
- element embedding similarity,
- screenshot-region similarity,
- accessible-tree similarity,
- learned target fingerprint matching.

This may reduce graph fragmentation in dynamic pages.

### Graph-based HITL steering
BrowserLens can be extended from read-only diagnosis to human-in-the-loop steering, where reviewers mark preferred paths, block repeated loops, or redirect agents from problematic states.

### Personalization and customization
Repeated user workflows could be extracted from graphs and used to customize browser-agent policies or navigation preferences.

### Failure dataset construction
Cue-highlighted trajectory segments can support the construction of browser-agent failure datasets and taxonomies.

### Automatic failure classification
The graph representation can provide features for models that classify failure types such as Navigation Stuck, Premature Stop, Wrong Page, Repeated No-op, or In-page Search Failure.

### Cross-run aggregate analysis
While BrowserLens focuses on single-run diagnosis, multiple trajectory graphs could be aggregated to compare agents, prompts, or tool policies across benchmark tasks.

### Action-layer rendering comparison
Future studies can compare the current action-as-node rendering with state-as-node/action-as-edge rendering. The latter may expose no-op self-loops more directly, while the former may better support repeated-action routine diagnosis.

---

## Revised Claim Summary

BrowserLens contributes a browser-state-anchored representation for single-run browser-agent diagnosis. It reconstructs a trajectory into URL, viewport, and state-anchored action graphs, surfaces structural and outcome cues, and lets reviewers verify those cues with browser-state evidence. The key claim is not that graph visualization alone solves browser-agent debugging, but that browser-agent trajectories become more diagnosable when ephemeral environment states are made explicit, persistent, and inspectable through a hierarchical graph representation.
