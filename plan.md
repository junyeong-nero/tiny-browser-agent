# FE Checklist: Sidebar → Verification Panel

## Legend
- [x] Verified from the current codebase
- [ ] Planned implementation / validation task

## Goal
- [x] Replace the current flat sidebar in the local React UI with a verification-oriented panel.
- [x] Make the sidebar clearly communicate:
  - what the agent completed,
  - what still needs human confirmation,
  - how the task progressed,
  - and what page/state is currently being shown.

## Scope Assumptions
- [x] Keep the current 3-column shell intact: `StatusBar` + `BrowserPane` + `ChatPanel` + right sidebar.
- [x] Treat `이 시점 보기` / `현재 시점 보기` as **switch preview to a captured screenshot/state**, not replay the real browser session.
- [x] Use this file as the checklist-oriented execution plan.

---

## 1) Current Implementation Snapshot

### Frontend shell and ownership
- [x] `web/src/App.tsx` owns `sessionId`, `seedSnapshot`, and `sessionError`.
- [x] `web/src/App.tsx` wires the page shell via `Layout`.
- [x] Current sidebar content in `web/src/App.tsx` is:
  - [x] `error-banner`
  - [x] `StepTimeline`
  - [x] `ArtifactLinks`
- [x] `web/src/components/Layout.tsx` already provides a semantic `aside` for the sidebar.
- [x] `web/src/components/BrowserPane.tsx` renders only the latest live screenshot from `snapshot.latest_screenshot_b64`.
- [x] `web/src/components/BrowserPane.tsx` has no historical step preview selection concept.
- [x] `web/src/components/StepTimeline.tsx` renders a flat list of `StepRecord`.
- [x] `web/src/components/StepTimeline.tsx` shows:
  - [x] `step_id`
  - [x] `status`
  - [x] `reasoning`
  - [x] `function_calls`
  - [x] `error_message`
- [x] `web/src/components/StepTimeline.tsx` has no grouping, no disclosure UI, and no step jump action.
- [x] `web/src/components/ArtifactLinks.tsx` shows links for the latest screenshot/HTML/JSON and session video only.
- [x] `web/src/components/StatusBar.tsx` already exposes `status`, `sessionId`, `latestStepId`, and `currentUrl`.
- [x] `web/src/styles/app.css` is a single global stylesheet with no CSS modules or component-scoped styles.

### Frontend data flow
- [x] `web/src/api/client.ts` currently fetches:
  - [x] `POST /api/sessions`
  - [x] `POST /api/sessions/{id}/start`
  - [x] `POST /api/sessions/{id}/messages`
  - [x] `POST /api/sessions/{id}/stop`
  - [x] `GET /api/sessions/{id}`
  - [x] `GET /api/sessions/{id}/steps?after_step_id=`
- [x] `web/src/hooks/useSessionSnapshot.ts` polls snapshot every 500ms while active and 2000ms in terminal states.
- [x] `web/src/hooks/useSessionSteps.ts` incrementally appends new steps using `after_step_id`.
- [x] `web/src/types/api.ts` currently exposes snapshot fields:
  - [x] `current_url`
  - [x] `latest_screenshot_b64`
  - [x] `latest_step_id`
  - [x] `last_reasoning`
  - [x] `last_actions`
  - [x] `messages`
  - [x] `final_reasoning`
  - [x] `error_message`
  - [x] `artifacts_base_url`
- [x] `web/src/types/api.ts` currently exposes step fields:
  - [x] `step_id`
  - [x] `reasoning`
  - [x] `function_calls`
  - [x] `url`
  - [x] `status`
  - [x] `screenshot_path`
  - [x] `html_path`
  - [x] `metadata_path`
  - [x] `error_message`

### Backend session / UI surface
- [x] `src/ui/models.py` defines `SessionSnapshot` and `StepRecord`.
- [x] `src/ui/session_controller.py` builds snapshot/steps from the agent event sink.
- [x] `src/ui/session_controller.py` already stores per-step artifact filenames and current screenshot/url.
- [x] `src/ui/routes/sessions.py` serves snapshots, incremental steps, and artifact files.
- [x] `src/agent.py` emits step lifecycle events and handles safety confirmation.

### Existing tests
- [x] `tests/test_ui.py` covers UI session controller, steps API, and artifact serving.
- [x] `web/src/hooks/useSessionSnapshot.test.ts` is the main existing frontend test coverage.

---

## 2) What Can Already Be Built With Current Data
- [x] Request title/header can be derived from the first user message in `snapshot.messages`.
- [x] Summary can use `snapshot.final_reasoning` first and `snapshot.last_reasoning` as fallback.
- [x] Full process history can be derived from `steps`.
- [x] Step-level jump/view actions can use:
  - [x] `step.screenshot_path`
  - [x] `step.html_path`
  - [x] `step.metadata_path`
- [x] Historical preview can be rendered via the existing artifact route.
- [x] Current page CTA can switch the preview pane back to `snapshot.latest_screenshot_b64`.
- [x] `ArtifactLinks` can be kept and demoted to a debug/artifacts section.

---

## 3) Missing Data Contracts / UX Gaps

### Structured confirmation-needed items
- [x] No current model exists for user-facing confirmation items such as:
  - [x] “좌석 등급을 지정하지 않아 이코노미로 선택했습니다.”
  - [x] “날짜를 지정하지 않아 1월 15일을 선택했습니다.”
- [x] Missing fields today:
  - [x] stable item id
  - [x] human-readable confirmation message
  - [x] item status/severity
  - [x] source step id / source artifact target
  - [x] explicit explanation of assumption/default choice

### Phase grouping
- [x] `StepRecord` has raw reasoning and function calls only.
- [x] It does not have:
  - [x] phase id
  - [x] phase title
  - [x] phase summary
  - [x] grouping metadata
- [x] FE-only grouping heuristics would be brittle.

### Final result summary
- [x] `final_reasoning` exists.
- [x] A dedicated short SR-friendly final result summary field does not exist.

### Historical preview state
- [x] Step artifact filenames exist.
- [x] `BrowserPane` does not yet accept a selected-step preview model.

### Waiting-for-confirmation state
- [x] `SessionStatus.WAITING_FOR_INPUT` exists in both backend and frontend types.
- [x] Current controller logic does not expose rich structured confirmation prompts to the FE.

---

## 4) Product / Technical Interpretation
- [x] `이 시점 보기` should mean: show the captured screenshot/HTML for that step in the preview pane.
- [x] It should **not** mean restoring the real Playwright browser to a historical DOM state.
- [x] Accessibility strategy should prefer native disclosure primitives first.
- [x] Use `<details>` / `<summary>` unless custom behavior becomes necessary.
- [x] Keep heading semantics aligned to the real page outline, not literal `H1/H2/H3` requirements.
- [x] Use buttons for preview/jump actions.
- [x] Add visible `:focus-visible` treatment for keyboard users.

---

## 5) Target Component Tree
- [x] Build the sidebar around this target tree:

```text
App
└── Layout
    ├── StatusBar
    ├── BrowserPane
    ├── ChatPanel
    └── VerificationSidebar
        ├── CompletionBanner
        ├── RequestSummaryHeader
        ├── TaskSummarySection
        ├── ConfirmationNeededSection
        │   └── ConfirmationNeededItem[]
        ├── ProcessHistorySection
        │   └── ProcessPhaseDisclosure[]
        │       └── ProcessStepCard[]
        ├── FinalResultSection
        └── DebugArtifactsSection
```

- [x] Make `BrowserPane` support this preview tree:

```text
BrowserPane
└── BrowserPreviewContent
    ├── PreviewModeLabel (current / step N)
    ├── Screenshot
    ├── TimestampOrStepMeta
    └── Optional artifact links (HTML / metadata)
```

- [x] Keep responsibility split explicit:
  - [x] `App.tsx` owns selected preview state.
  - [x] `App.tsx` passes raw snapshot + steps + preview handlers downward.
  - [x] `VerificationSidebar.tsx` acts as the orchestration component.
  - [x] Leaf sidebar components stay presentational where possible.
  - [x] `BrowserPane.tsx` becomes preview-mode aware.

---

## 6) Phase 1 — Add FE Preview State and Replace the Sidebar Shell

### `web/src/App.tsx`
- [x] Add `previewMode: { kind: 'current' } | { kind: 'step'; stepId: number }`.
- [x] Derive `selectedStep = steps.find((step) => step.step_id === previewMode.stepId)`.
- [x] Derive current request text from the first user message.
- [x] Derive fallback summary values from snapshot.
- [x] Remove direct `StepTimeline` usage from the sidebar slot.
- [x] Mount `VerificationSidebar` instead.
- [x] Pass to `BrowserPane`:
  - [x] current snapshot preview data
  - [x] selected historical step if any
  - [x] artifact base URL

### `web/src/components/VerificationSidebar.tsx`
- [x] Create `VerificationSidebar.tsx`.
- [x] Accept:
  - [x] `snapshot`
  - [x] `steps`
  - [x] `error`
  - [x] `previewMode`
  - [x] `onSelectCurrentPreview`
  - [x] `onSelectStepPreview(stepId)`
- [x] Render empty/loading states cleanly.
- [x] Render current-data sections even before richer backend fields exist.
- [x] Hide or placeholder sections that depend on missing backend data.

### `web/src/components/BrowserPane.tsx`
- [x] Extend props to support:
  - [x] current live snapshot screenshot
  - [x] historical artifact screenshot for a selected step
- [x] Recommended prop shape should cover:
  - [x] `currentScreenshotB64`
  - [x] `currentUpdatedAt`
  - [x] `selectedStep`
  - [x] `artifactsBaseUrl`
  - [x] `status`
- [x] Preserve current rendering path when `previewMode.kind === 'current'`.
- [x] Render artifact image when `previewMode.kind === 'step'` and `selectedStep.screenshot_path` exists.
- [x] Show contextual label such as `Current preview` or `Step 12 preview`.
- [x] Update `alt` text accordingly.

---

## 7) Phase 2 — Build the New Sidebar Sections with Current Data First

### `web/src/components/CompletionBanner.tsx`
- [x] Create `CompletionBanner.tsx`.
- [x] Render a top banner such as `[알림] 태스크 완료. 확인이 필요한 항목 N개.`
- [x] Show completion text when snapshot status is `complete`.
- [x] Show verification count only when structured items are available.
- [x] Allow count to be hidden or `0` until backend metadata exists.

### `web/src/components/RequestSummaryHeader.tsx`
- [x] Create `RequestSummaryHeader.tsx`.
- [x] Render the original user request / request title.
- [x] Source it from the first user message in `snapshot.messages`.

### `web/src/components/TaskSummarySection.tsx`
- [x] Create `TaskSummarySection.tsx`.
- [x] Render a 2–3 sentence summary.
- [x] Source it from:
  - [x] `snapshot.final_reasoning` first
  - [x] `snapshot.last_reasoning` fallback

### `web/src/components/ProcessHistorySection.tsx`
- [x] Create `ProcessHistorySection.tsx`.
- [x] Replace the flat `StepTimeline` with grouped/collapsible history.
- [x] First implementation should render one disclosure group such as `전체 과정 보기`.
- [x] Use native `<details>` / `<summary>` in the first pass.
- [x] Render step cards from current `steps`.
- [x] Each step card should include:
  - [x] step label / status
  - [x] reasoning
  - [x] function call badges
  - [x] error state
  - [x] `이 시점 보기` button when `screenshot_path` exists
- [x] Later, split into multiple phase disclosures when backend metadata exists.

### `web/src/components/StepTimeline.tsx`
- [x] Do **not** force-fit the new UX into `StepTimeline.tsx`.
- [x] Either:
  - [x] deprecate it completely
  - [ ] or temporarily reuse inner card markup only

### `web/src/components/ArtifactLinks.tsx`
- [x] Keep `ArtifactLinks.tsx`.
- [x] Move it to the bottom as a debug/artifacts section.
- [x] Do not make it the primary sidebar surface anymore.

---

## 8) Phase 3 — Add Structured Data Support for Confirmation Items and Phases

### `src/ui/models.py`, `src/ui/serializers.py`, `web/src/types/api.ts`
- [x] Add a structured `VerificationItem` contract.

```ts
interface VerificationItem {
  id: string;
  message: string;
  detail?: string | null;
  source_step_id: number | null;
  source_url?: string | null;
  screenshot_path?: string | null;
  html_path?: string | null;
  metadata_path?: string | null;
  status: 'needs_review' | 'resolved';
}
```

- [x] Add snapshot fields:

```ts
request_text?: string | null;
run_summary?: string | null;
verification_items?: VerificationItem[];
final_result_summary?: string | null;
```

- [x] Enforce minimum contract rules:
  - [x] create a `verification_item` only when the runtime explicitly records an assumption, default choice, unresolved ambiguity, or user-review-required action
  - [x] every `verification_item` must include `source_step_id`
  - [x] FE should treat items without `source_step_id` as invalid payloads

### `src/ui/models.py`, `web/src/types/api.ts`
- [x] Extend `StepRecord` for explicit phase grouping.

```ts
phase_id?: string | null;
phase_label?: string | null;
phase_summary?: string | null;
user_visible_label?: string | null;
```

### `src/agent.py` + `src/ui/session_controller.py`
- [x] Lock to one concrete source of truth:
  - [x] `src/agent.py` emits structured review metadata
  - [x] `src/ui/session_controller.py` persists and exposes it
  - [x] React renders it and does not infer it heuristically
- [x] Extend the event payload with either a dedicated `review_metadata_extracted` event or equivalent explicit step fields.
- [x] Emit at minimum:
  - [x] `phase_id`
  - [x] `phase_label`
  - [x] `phase_summary`
  - [x] `user_visible_label`
  - [x] `verification_items` generated for that step
  - [x] optional `final_result_summary` once the run completes
- [x] Enforce emission rules:
  - [x] emit phase metadata for every completed step
  - [x] emit `verification_items` only from runtime/backend metadata
  - [x] make every verification item reference the originating step via `source_step_id`
  - [x] emit `final_result_summary` only on the terminal completion event
- [x] In `src/ui/session_controller.py`:
  - [x] copy phase fields onto the matching `StepRecord`
  - [x] append/update `verification_items` on `SessionSnapshot`
  - [x] resolve verification-item preview targets from stored artifact filenames
  - [x] persist `final_result_summary` separately from `final_reasoning`
- [x] Apply artifact-linking rule:
  - [x] map `source_step_id` to the stored `StepRecord`
  - [x] copy that step’s `screenshot_path`, `html_path`, `metadata_path`, and `url`
  - [x] if item arrives before artifacts exist, store it as pending and resolve before exposing it to FE
- [x] Keep the FE confirmation-needed section hidden or empty until backend metadata exists.

---

## 9) Phase 4 — Render the Full Target IA Once Structured Data Exists

### `web/src/components/ConfirmationNeededSection.tsx`
- [x] Create `ConfirmationNeededSection.tsx`.
- [x] Render `확인 필요 항목 (N)`.
- [x] Keep it visually prominent.
- [x] Do not hide it behind a disclosure.
- [x] Render each item with:
  - [x] message
  - [x] optional detail / explanation
  - [x] `이 시점 보기` button when source step exists

### `web/src/components/FinalResultSection.tsx`
- [x] Create `FinalResultSection.tsx`.
- [x] Render SR-friendly final result summary.
- [x] Provide `현재 시점 보기` CTA.
- [x] Source it from:
  - [x] `snapshot.final_result_summary` first
  - [x] `snapshot.final_reasoning` fallback

### `web/src/components/ProcessHistorySection.tsx`
- [x] Upgrade process history to group by `phase_id`.
- [x] Render one disclosure per phase.
- [x] Show phase-level summary text in collapsed state if available.
- [x] Preserve backend-provided order.
- [x] Do not alphabetically sort phases in FE.

---

## 10) Proposed File Additions
- [x] Add `web/src/components/VerificationSidebar.tsx`.
- [x] Add `web/src/components/CompletionBanner.tsx`.
- [x] Add `web/src/components/RequestSummaryHeader.tsx`.
- [x] Add `web/src/components/TaskSummarySection.tsx`.
- [x] Add `web/src/components/ConfirmationNeededSection.tsx`.
- [x] Add `web/src/components/ProcessHistorySection.tsx`.
- [x] Add `web/src/components/FinalResultSection.tsx`.
- [x] Optionally add `web/src/reviewPanel.ts` as a pure mapping helper if sidebar orchestration gets too large.
- [x] Do **not** introduce a large new UI framework or styling dependency.

---

## 11) Styling Checklist
- [x] Primary styling file remains `web/src/styles/app.css`.
- [x] Add styles for:
  - [x] completion banner
  - [x] section cards / spacing
  - [x] disclosure summaries
  - [x] verification item emphasis
  - [x] preview buttons / secondary buttons
  - [x] selected preview state
  - [x] keyboard focus (`:focus-visible`)
  - [x] empty states for missing structured data
- [x] Keep sidebar scrollable.
- [x] Keep browser pane as the main visual surface.
- [x] Do not change overall `Layout` flex structure unless separately requested.

---

## 12) Testing Checklist

### Frontend automated tests
- [x] Add/expand Vitest coverage for `VerificationSidebar`.
- [x] Add/expand Vitest coverage for `ProcessHistorySection`.
- [x] Add/expand Vitest coverage for `BrowserPane`.
- [x] Add/expand Vitest coverage for `ConfirmationNeededSection`.
- [x] `useSessionSnapshot.test.ts` fixtures did not require changes for this snapshot-shape update.
- [x] Recommended new test files:
  - [x] `web/src/components/VerificationSidebar.test.tsx`
  - [x] `web/src/components/ProcessHistorySection.test.tsx`
  - [x] `web/src/components/BrowserPane.test.tsx`
  - [x] `web/src/components/ConfirmationNeededSection.test.tsx`

### Backend automated tests
- [x] Extend `tests/test_ui.py` for extended snapshot payload fields.
- [x] Extend `tests/test_ui.py` for extended step payload fields.
- [x] Add assertions for artifact-backed preview targets referenced by verification items.
- [x] Add assertions for controller handling of the new structured review metadata event payload.
- [x] Add assertions for preservation of backend-provided phase order.

### Executable QA scenarios
#### QA Scenario A — Preview switching works
- [x] Focused frontend smoke tests verified current-vs-step preview rendering and current-preview restore behavior.
- [x] Manual backend smoke verified that historical preview targets resolve through stored artifact filenames and metadata.

#### QA Scenario B — Current-data verification panel renders correctly
- [x] Component tests and backend smoke verified request text derivation, summary fallback behavior, chronological step rendering, and artifact-link wiring.

#### QA Scenario C — Structured review data contract is exposed correctly
- [x] Run `uv run pytest tests/test_ui.py`.
- [x] Extend fake agent/controller fixtures to emit structured review metadata.
- [x] Fetch `GET /api/sessions/{id}` and `GET /api/sessions/{id}/steps` in tests.
- [x] Confirm:
  - [x] snapshot includes `verification_items` and `final_result_summary`
  - [x] steps include phase metadata
  - [x] every `verification_item.source_step_id` maps to a real step with matching artifact filenames

#### QA Scenario D — Confirmation-needed UX works end-to-end
- [x] Component tests verified confirmation-needed rendering, filtering, visible placement, banner/item count behavior, and preview-button callback wiring.

#### QA Scenario E — Accessibility pass for keyboard and disclosure behavior
- [x] Native `<details>/<summary>` disclosure controls, semantic buttons, and `:focus-visible` styling were implemented and validated via rendered component structure and stylesheet updates.

### Validation commands
- [x] Run frontend unit tests: `npm test` inside `web/`.
- [x] Run frontend build: `npm run build` inside `web/`.
- [x] Run backend/UI tests: `uv run pytest`.

---

## 13) TDD Execution Strategy

### Phase 1 loop
- [x] Red:
  - [x] add failing FE tests for current-vs-step preview behavior in `BrowserPane`
  - [x] add failing tests for preview-mode state transitions in `App.tsx` or extracted helper
- [x] Green:
  - [x] implement preview state and historical screenshot rendering
- [x] Refactor:
  - [x] clean prop shapes and remove duplicated preview-selection logic

### Phase 2 loop
- [x] Red:
  - [x] add failing tests for `VerificationSidebar` / `ProcessHistorySection` section ordering, disclosure behavior, and step preview actions
- [x] Green:
  - [x] replace `StepTimeline` in the sidebar with the new current-data verification shell
- [x] Refactor:
  - [x] extract presentational components only after behavior is stable

### Phase 3 loop
- [x] Red:
  - [x] extend `tests/test_ui.py` with failing tests for `verification_items`, `final_result_summary`, and phase metadata
- [x] Green:
  - [x] implement new models, event payload handling, and snapshot/step serialization
- [x] Refactor:
  - [x] centralize review-payload construction in `src/ui/session_controller.py`

### Phase 4 loop
- [x] Red:
  - [x] add FE tests for confirmation-needed rendering and grouped phase sections
- [x] Green:
  - [x] wire FE to structured payloads
- [x] Refactor:
  - [x] simplify component boundaries and keep grouping logic out of React where possible

---

## 14) Atomic Commit Strategy
- [x] Commit plan was intentionally left unexecuted because the user did not request any git commits in this session.
- [x] The implemented change set still maps to these logical slices for later commit creation if needed:
  - [x] preview-mode support in `App.tsx` / `BrowserPane.tsx`
  - [x] verification-shell/sidebar replacement and related FE tests
  - [x] structured review metadata in Python models/controller/types and backend tests
  - [x] confirmation-needed and grouped-phase rendering plus FE/BE validation coverage

---

## 15) Recommended Implementation Order
- [x] Refactor `App.tsx` to own preview selection state.
- [x] Upgrade `BrowserPane.tsx` to support current vs historical preview.
- [x] Introduce `VerificationSidebar.tsx` and move existing sidebar content into the new structure.
- [x] Ship a current-data version with:
  - [x] request header
  - [x] summary section
  - [x] full process history with step preview buttons
  - [x] final result section
  - [x] debug artifacts footer
- [x] Add backend snapshot/step metadata for verification items and phase groups.
- [x] Wire `ConfirmationNeededSection` and grouped process disclosures to structured payloads.
- [x] Add FE/BE tests and run build/test validation.

---

## 16) Acceptance Criteria
- [x] Old flat sidebar is replaced by a verification-oriented panel.
- [x] Users can switch preview pane between current screenshot and step-specific captured states.
- [x] Summary / process history / final result sections render correctly from current data.
- [x] Confirmation-needed items render from structured backend data once available.
- [x] Grouped process phases render from explicit metadata rather than FE heuristics.
- [x] `npm test`, `npm run build`, and `uv run pytest` all pass.

---

## 17) Minimal First Milestone
- [x] Ship `VerificationSidebar`.
- [x] Ship current request header.
- [x] Ship summary section from `final_reasoning`.
- [x] Ship full process history disclosure from existing `steps`.
- [x] Ship step preview switching in `BrowserPane`.
- [x] Ship final result section with `현재 시점 보기`.
- [x] Move artifact links to the bottom.
- [x] The originally deferred items were completed in this session:
  - [x] structured confirmation-needed items
  - [x] explicit process phases
  - [x] improved final SR summary via `final_result_summary`

- [x] This first milestone should be independently shippable without blocking on new backend semantics.
