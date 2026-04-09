
# Refactoring Plan — Repo-Aligned Verification Panel

기반 레포: [junyeong-nero/computer-use-preview](https://github.com/junyeong-nero/computer-use-preview)

이 문서는 **현재 레포 상태에 맞춰** verification panel 개선 계획을 다시 정리한 것이다.

## 현재 레포 기준으로 바로 반영한 전제

- 이 레포는 이미 **FastAPI + React UI** 를 갖고 있다.
  - 백엔드: `src/ui/server.py`, `src/ui/routes/sessions.py`
  - 프론트엔드: `web/src/`
- verification UI는 신규가 아니라 이미 존재한다.
  - `web/src/components/VerificationSidebar.tsx`
  - `web/src/components/ConfirmationNeededSection.tsx`
  - `web/src/components/ProcessHistorySection.tsx`
  - `web/src/reviewPanel.ts`
- step review metadata 흐름도 이미 존재한다.
  - `src/agent.py` 에서 `phase_id`, `phase_label`, `phase_summary`, `user_visible_label`, `verification_items` emit
  - `src/ui/session_controller.py` 에서 이를 `StepRecord`, `SessionSnapshot` 에 반영
- Playwright 로그 구조는 두 가지다.
  - CLI: `logs/history/<timestamp>/...`
  - UI session: `logs/history/ui/<session-id>/...`
- 현재 `pyproject.toml` 의 Playwright 버전은 `1.55.0` 이다.
  - 따라서 Phase 2는 `page.accessibility.snapshot()` 이 아니라 **`page.locator("body").ariaSnapshot()`** 기준으로 설계한다.
  - `page.ariaSnapshot()` 은 현재 pinned version 기준으로 사용할 수 없다.

---

## 목표 재정의

기존 verification sidebar를 확장해서 아래를 제공한다.

1. step별 ambiguity / review 근거를 더 명확히 표시
2. step별 접근성 스냅샷 artifact를 함께 저장하고 재생성 없이 조회
3. 기존 `phase_*` metadata를 우선 활용하면서, 필요 시 추가 grouping payload를 제공
4. screen-reader 친화적인 verification panel UX로 점진 개선

---

## Phase 1. Existing metadata pipeline 확장

**목표**: 지금 있는 `review_metadata_extracted` / `VerificationItem` / `StepRecord` 흐름을 유지하면서 ambiguity 관련 정보와 a11y artifact 경로를 실을 수 있게 만든다.

**핵심 원칙**

- 새 구조를 따로 만드는 대신 기존 `src/agent.py` → `src/ui/session_controller.py` 흐름을 확장한다.
- ambiguity는 “확정 판정”이 아니라 **review candidate / heuristic flag** 로 다룬다.
- 첫 단계에서는 LLM 기반 판정보다 **rule-based evidence 수집** 을 우선한다.

**구현 위치**

- `src/agent.py`
- `src/ui/models.py`
- `src/ui/session_controller.py`
- 필요 시 신규: `src/ambiguity_detector.py`

**체크리스트**

- [x] `src/ui/models.py` 의 `StepRecord` 에 아래 후보 필드 추가 여부 결정 및 반영
  - `ambiguity_flag: bool | None`
  - `ambiguity_type: str | None`
  - `ambiguity_message: str | None`
  - `a11y_path: str | None`
- [x] `src/ui/models.py` 의 `VerificationItem` 에도 `a11y_path: str | None` 추가 여부 검토 후 반영
- [x] `src/agent.py::_enrich_persisted_action_metadata()` 가 step metadata JSON에 ambiguity / a11y 관련 필드를 병합할 수 있게 확장
- [x] `src/agent.py::_emit_review_metadata()` payload 확장 방안 정리
  - ambiguity candidate 정보
  - run summary와 별개인 review evidence
- [x] 신규 `src/ambiguity_detector.py` 생성 여부 결정
  - 생성 시: pure function 위주로 구성
  - 미생성 시: `src/agent.py` 내부 helper로 시작
- [x] 첫 버전 ambiguity rule을 아래 수준으로 제한
  - query에 없는 구체값 입력 시 candidate 생성
  - 동일 맥락에서 반복 click/type 발생 시 candidate 생성
  - 명시적 `navigate` 없이 URL 변화 시 candidate 생성
- [x] 각 rule은 반드시 **evidence string** 을 남기도록 설계
  - 예: `typed_text_not_in_query`
  - 예: `url_changed_without_navigate`
  - 예: `repeated_click_pattern`
- [x] false positive를 줄이기 위해 아래는 Phase 1에서 제외
  - “모호성 확정 판정”
  - LLM 자동 해석
  - 복잡한 intent inference

**테스트 체크리스트**

- [x] `tests/test_playwright_logging.py` 에 metadata enrichment 확장 케이스 추가
- [x] `tests/test_ui.py` 에 `review_metadata_extracted` payload 확장 반영 테스트 추가
- [x] ambiguity detector를 별도 파일로 만들면 전용 unit test 추가

---

## Phase 2. A11y artifact 저장을 현재 Playwright/로그 구조에 맞게 추가

**목표**: step snapshot이 저장될 때 screenshot / html / metadata와 함께 **ARIA snapshot artifact** 도 같이 저장한다.

**중요한 기술 제약**

- 현재 레포는 `playwright==1.55.0`
- 따라서 사용 API는 `page.locator("body").ariaSnapshot()`
- `page.accessibility.snapshot()` 전제는 제거
- snapshot 원본은 JSON object가 아니라 **YAML string** 이므로 raw payload 보존이 우선

**구현 위치**

- `src/computers/playwright/playwright.py`
- `src/tool_calling.py`
- `src/ui/session_controller.py`
- `src/ui/models.py`

**저장 구조 제안**

```text
logs/history/<timestamp>/history/
├── step-0006.png
├── step-0006.html
├── step-0006.json
└── step-0006.a11y.yaml
```

UI session도 동일한 파일 구조를 유지하되 루트만 `logs/history/ui/<session-id>/history/` 로 둔다.

**체크리스트**

- [x] `src/computers/playwright/playwright.py::_write_history_snapshot()` 에 a11y snapshot 저장 추가
- [x] `page.locator("body").ariaSnapshot()` 호출 실패 시 graceful fallback 정의
  - 실패해도 기존 screenshot/html/json 저장은 유지
  - metadata에는 `a11y_capture_error` 또는 null path 기록
- [x] a11y artifact 파일명 규칙 확정
  - 권장: `step-XXXX.a11y.yaml`
- [x] 기존 metadata JSON(`step-XXXX.json`) 에 `a11y_path` 필드 추가
- [x] `PlaywrightComputer._latest_artifact_metadata` 에 `a11y_path` 포함
- [x] `src/tool_calling.py` 의 artifact 전달 흐름이 `a11y_path` 를 포함하도록 유지 확인
- [x] `src/ui/session_controller.py` 에서 `StepRecord` / `VerificationItem` resolve 시 `a11y_path` 반영
- [x] artifact 조회는 **기존** `GET /api/sessions/{session_id}/artifacts/{name}` 를 재사용
- [x] 별도 `/steps/{step_id}/a11y` endpoint는 **초기 구현 범위에서 제외**

**a11y artifact 내용 원칙**

- [x] raw YAML string을 우선 저장
- [x] 필요 metadata는 기존 `step-XXXX.json` 에 저장
  - `a11y_path`
  - `a11y_source` (`body_locator_aria_snapshot`)
  - `a11y_capture_status`
- [x] Phase 2에서는 YAML → custom JSON tree 변환까지 한 번에 하지 않음

**테스트 체크리스트**

- [x] `tests/test_playwright_logging.py` 에 `step-XXXX.a11y.yaml` 생성 테스트 추가
- [x] a11y capture 실패 시에도 기존 history artifact가 남는지 테스트 추가
- [x] `tests/test_ui.py` 에 `a11y_path` 가 session snapshot / step resolution으로 전달되는지 확인

---

## Phase 3. Existing phase metadata를 우선 활용하는 verification payload 구성

**목표**: 기존 `phase_id`, `phase_label`, `phase_summary`, `user_visible_label` 흐름을 버리지 않고, verification panel 전용 payload를 만들어 UI에서 더 읽기 좋게 만든다.

**핵심 원칙**

- 별도 structurer는 만들 수 있지만, **기존 phase metadata를 1차 source of truth** 로 사용한다.
- URL/action 기반 grouping은 fallback이다.
- 첫 버전은 rule-based only로 시작하고, LLM 보조는 미결 사항으로 남긴다.

**구현 위치**

- 신규 권장: `src/ui/verification_service.py`
- 또는 기존 `src/ui/session_controller.py` 내부 helper
- `src/ui/routes/sessions.py`

**payload 방향**

- raw step list는 계속 `GET /api/sessions/{id}/steps` 로 제공
- grouped verification payload가 필요하면 `GET /api/sessions/{id}/verification` 추가
- a11y 실제 파일은 artifact route로 fetch

**체크리스트**

- [x] verification payload 생성 위치 확정
  - 권장: `src/ui/verification_service.py`
- [x] 입력 source 확정
  - `SessionController.get_steps()` 결과
  - `SessionSnapshot.verification_items`
- [x] group 생성 우선순위 정의
  1. 기존 `phase_id`
  2. 없으면 URL 변화
  3. 없으면 action sequence 변화
- [x] loop compression은 바로 자동 적용하지 말고, first version은 아래 수준으로 제한
  - 반복 step count 표시
  - summary 문구에 “N회 반복” 포함
  - 원본 step list는 항상 보존
- [x] group summary는 first version에서 rule-based template 사용
- [x] LLM summary generation은 미결 사항으로 남기고 기본 구현 범위에서 제외
- [x] verification payload 안에 아래 항목 포함
  - request text
  - run summary
  - final result summary
  - grouped steps
  - verification items
  - 각 step/group의 artifact path
- [x] `src/ui/routes/sessions.py` 에 `GET /api/sessions/{id}/verification` 추가 여부 결정 후 구현
- [x] endpoint를 추가하지 않는 경우, 기존 snapshot + steps 조합만으로 UI 렌더 가능한지 먼저 검증

**테스트 체크리스트**

- [x] `tests/test_ui.py` 에 grouped verification payload 테스트 추가
- [x] 기존 `phase_id` 가 있을 때 group이 안정적으로 유지되는지 테스트 추가
- [x] phase metadata가 없을 때 URL/action fallback group 생성 테스트 추가

---

## Phase 4. Existing React verification sidebar를 SR-friendly panel로 확장

**목표**: 새 UI를 처음부터 만드는 대신, 현재 `VerificationSidebar` 를 확장해서 screen-reader 친화적인 verification panel 경험을 만든다.

**구현 위치**

- `web/src/App.tsx`
- `web/src/components/VerificationSidebar.tsx`
- `web/src/components/ConfirmationNeededSection.tsx`
- `web/src/components/ProcessHistorySection.tsx`
- 신규 권장: `web/src/components/AccessibilityTreeView.tsx`
- 신규 권장: `web/src/hooks/useKeyboardFocusSwitch.ts`
- `web/src/types/api.ts`
- `web/src/reviewPanel.ts`

**UI 방향**

- 왼쪽: 기존 브라우저 프리뷰 유지
- 오른쪽: 기존 verification sidebar를 panel 모드로 개선
- “확인 필요 항목” 에서 해당 step screenshot + html + a11y artifact 접근 제공
- “과정 기록” 은 기존 `details/summary` 구조를 유지하되 정보 밀도와 SR 텍스트를 개선

**체크리스트**

- [x] `web/src/types/api.ts` 에 backend model 확장 반영
  - `a11y_path`
  - ambiguity 관련 필드
- [x] `VerificationSidebar` 를 신규 생성 대신 기존 컴포넌트 확장으로 진행
- [x] `CompletionBanner` 에 SR-friendly 상태 문구 재검토
  - 필요 시 live region role/attribute 추가
- [x] `ConfirmationNeededSection` 에 review evidence / ambiguity type / a11y artifact 진입점 추가
- [x] `ProcessHistorySection` 에 step별 a11y artifact 링크 또는 inline viewer 진입점 추가
- [x] 신규 `AccessibilityTreeView` 컴포넌트 추가
  - 입력은 raw YAML string 또는 서버 가공 텍스트
  - first version은 read-only viewer 우선
- [x] artifact fetch 방식 확정
  - 권장: 기존 `artifacts_base_url` + `a11y_path`
- [x] 포커스 전환은 `Alt+Tab` 대신 커스텀 shortcut 또는 명시적 버튼 사용
  - 예: `Alt+Shift+V` / `Alt+Shift+B`
  - shortcut 없이도 버튼만으로 동일 기능 가능해야 함
- [x] 모든 토글/펼치기 UI는 `aria-expanded`, `aria-controls` 유지 또는 보강
- [x] 완료 시점 안내 문구는 live region으로 제공하되 과도한 assertive 남용은 피함

**테스트 체크리스트**

- [x] `web/src/components/VerificationSidebar.test.tsx` 확장
- [x] `web/src/components/ConfirmationNeededSection.test.tsx` 에 a11y artifact 진입 테스트 추가
- [x] `web/src/components/ProcessHistorySection.test.tsx` 에 group/preview/a11y 링크 테스트 추가
- [x] 신규 `AccessibilityTreeView` 테스트 추가

---

## 구현 순서 / 의존성

```text
Phase 1. metadata pipeline 확장
    ↓
Phase 2. a11y artifact 저장
    ↓
Phase 3. verification payload 구성
    ↓
Phase 4. existing sidebar 확장
```

### 의존성 메모

- Phase 2는 Phase 1의 model field 결정이 선행되면 깔끔하다.
- Phase 3는 기존 phase metadata를 활용하므로 Phase 1이 선행될수록 구현이 단순해진다.
- Phase 4는 Phase 2의 `a11y_path` 와 Phase 3의 payload 방향이 정리된 뒤 진행한다.

---

## 범위 밖으로 명시하는 항목

- [ ] LLM 기반 ambiguity 확정 판정
- [ ] full accessibility audit (axe-core 통합)
- [ ] 자동 root-cause explanation 생성
- [ ] multi-tab / multi-page verification model 확장

---

## 미결 사항

- [x] `a11y_path` 는 `StepRecord` 와 `VerificationItem` 양쪽에 반영
- [x] `GET /api/sessions/{id}/verification` endpoint 추가
- [x] ambiguity rule은 별도 파일로 분리하지 않고 `src/agent.py` helper로 유지
- [x] a11y YAML은 서버 변환 없이 프론트 read-only viewer로 노출
- [x] keyboard shortcut 기본값 없이 버튼 기반 포커스 이동만 제공

---

## 완료 기준

- [x] step artifact에 screenshot / html / metadata / a11y가 함께 저장된다
- [x] UI session과 CLI logging 경로 모두에서 artifact naming이 일관된다
- [x] 기존 verification sidebar가 새 payload/fields를 읽어 SR-friendly panel로 동작한다
- [x] 기존 tests + 신규 tests가 모두 통과한다
