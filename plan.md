# Method 2 + BrowserPane 역할 재정의 체크리스트

## 전체 목표

- [x] `web -> /api -> FastAPI` 구조를 `web -> desktop bridge(IPC) -> Python app service` 구조로 전환한다.
- [x] `src/ui/session_controller.py` 중심의 런타임 코어를 유지한다.
- [x] `BrowserPane`를 스크린샷 뷰어가 아니라 **live browser surface host/controller**로 재정의한다.
- [x] side panel / chat / browser surface 사이 포커스를 단축키와 명시적 focus manager로 이동할 수 있게 한다.
- [x] artifact 접근을 `/api/...` URL 조합에서 bridge API 기반 접근으로 전환한다.

## 비목표

- [x] `BrowserAgent`의 추론 로직을 대규모로 재작성하지 않는다.
- [x] 1차 단계에서 polling을 push/event streaming으로 완전히 교체하지 않는다.
- [x] OS 전체(native accessibility tree)까지 바로 일반화하지 않는다.
- [x] 모든 desktop shell(Electron/Tauri/기타)을 동시에 지원하지 않는다.

## 현재 구조 요약

### 유지할 핵심 코어

- [x] `src/ui/session_controller.py`
- [x] `src/ui/session_store.py`
- [x] `src/ui/models.py`의 상태 모델 (`SessionSnapshot`, `StepRecord`, `VerificationPayload` 등)
- [x] `src/agent.py`
- [x] `src/tool_calling.py`
- [x] `src/computers/computer.py`

### 교체/삭제 대상

- [x] `src/ui/server.py`
- [x] `src/ui/routes/sessions.py`
- [x] `web/src/api/client.ts`의 `fetch('/api/...')` 중심 구현
- [x] `artifacts_base_url` + `buildArtifactUrl()` 중심 artifact 접근 흐름

### 새로 도입할 요소

- [x] transport-neutral Python service 계층
- [x] desktop IPC bridge
- [x] browser surface host abstraction
- [x] 앱 전역 focus manager
- [x] artifact bridge API

## 목표 아키텍처

```text
React UI
  ├─ SessionClient interface
  ├─ FocusManager
  ├─ BrowserPane (live browser surface host/controller)
  ├─ ChatPanel
  └─ VerificationSidebar
           │
           │ desktop bridge / IPC
           ▼
Desktop Shell
  ├─ BrowserSurfaceHost
  └─ Python bridge
           │
           ▼
Python SessionService
  └─ SessionStore
      └─ SessionController
          └─ BrowserAgent
              └─ Computer
```

## Phase 0. Feasibility Spike: live browser surface 전략 확정

### 목표

- [x] 앱 안에서 실제 interactive browser surface를 어떻게 호스팅할지 결정한다.

### 결정 메모

- [x] BrowserPane은 host container를 선언하고, shell(Electron)이 소유한 `WebContentsView`를 해당 bounds에 overlay한다.
- [x] Python 런타임은 `ElectronSurfaceComputer` + Electron command bridge를 통해 shell-owned surface를 제어한다.
- [x] live surface가 없을 때만 screenshot fallback을 노출한다.

### 체크리스트

- [x] shell이 소유한 browser surface를 `Computer` backend가 제어할 수 있는지 확인한다.
- [x] 기존 `PlaywrightComputer` 확장 vs 새 `DesktopBrowserComputer` 도입 중 하나를 선택한다.
- [ ] shell-owned browser를 CDP 등으로 attach 가능한지 검증한다.
- [x] 실패 시 fallback UX를 정의한다.
- [x] BrowserPane이 DOM에 직접 embed되는지, shell이 native surface를 overlay하는지 결정한다.

### 참고 파일

- [x] `src/computers/playwright/playwright.py`
- [x] `src/computers/browserbase/browserbase.py`

### 산출물 / 완료 기준

- [x] 브라우저 surface 호스팅 방식이 1개로 확정된다.
- [x] 새 `Computer` backend 필요 여부가 명확해진다.
- [x] BrowserPane의 live surface 전략이 문서화된다.

## Phase 1. Python app service 추출

### 목표

- [x] FastAPI route가 하던 일을 transport-neutral service 계층으로 이동한다.

### 신규 후보 파일

- [x] `src/ui/session_service.py`

### 체크리스트

- [x] `create_session()`를 service에 정의한다.
- [x] `start_session(session_id, query)`를 service에 정의한다.
- [x] `send_message(session_id, text)`를 service에 정의한다.
- [x] `stop_session(session_id)`를 service에 정의한다.
- [x] `get_snapshot(session_id)`를 service에 정의한다.
- [x] `get_steps(session_id, after_step_id=None)`를 service에 정의한다.
- [x] `get_verification(session_id)`를 service에 정의한다.
- [x] `resolve_artifact(...)` / `read_artifact_text(...)` / `read_artifact_bytes(...)` 중 최종 API를 정한다.
- [x] `src/ui/routes/sessions.py`가 controller 직접 호출 대신 service만 호출하도록 바꾼다.
- [x] `src/ui/session_store.py`를 service에서 쓰기 쉬운 얇은 manager로 유지한다.
- [x] `src/ui/models.py`에서 상태 모델과 HTTP DTO 분리 방향을 정리한다.

### 주의사항

- [x] 이 단계에서는 기존 HTTP 동작을 깨지 않는다.
- [x] 기존 테스트가 계속 통과하도록 route -> service -> controller 구조만 정리한다.

### 완료 기준

- [x] HTTP layer가 service를 통하도록 바뀐다.
- [x] service가 desktop bridge에서 직접 쓸 수 있는 형태가 된다.

## Phase 2. Frontend transport abstraction 도입

### 목표

- [x] React 앱이 `fetch('/api/...')`에 직접 묶이지 않게 한다.

### 신규 후보 파일

- [x] `web/src/api/sessionClient.ts`
- [x] `web/src/api/httpSessionClient.ts`
- [x] `web/src/api/desktopSessionClient.ts`
- [x] `web/src/api/SessionClientContext.tsx` 또는 유사 provider

### 체크리스트

- [x] 현재 `apiClient` 메서드 표면을 interface로 추출한다.
- [x] 기존 HTTP 구현을 `httpSessionClient`로 옮긴다.
- [x] desktop shell용 `desktopSessionClient` 계약을 정의한다.
- [x] 앱이 provider/context를 통해 `SessionClient`를 주입받도록 바꾼다.
- [x] `web/src/hooks/useSessionSnapshot.ts`가 transport-agnostic client를 사용하게 한다.
- [x] `web/src/hooks/useSessionSteps.ts`가 transport-agnostic client를 사용하게 한다.
- [x] `web/src/hooks/useSessionVerification.ts`가 transport-agnostic client를 사용하게 한다.
- [x] `web/src/hooks/useSessionControls.ts`가 transport-agnostic client를 사용하게 한다.
- [x] `web/src/hooks/useSendMessage.ts`가 transport-agnostic client를 사용하게 한다.
- [x] `web/src/App.tsx`에서 `apiClient.createSession()` 직접 호출을 추상화된 client로 바꾼다.

### 원칙

- [x] 1차 단계에서는 polling을 유지한다.
- [x] 훅의 책임은 유지하고 transport만 교체한다.

### 완료 기준

- [x] React 앱이 HTTP client/desktop client를 교체 가능하게 된다.
- [x] UI 훅 로직은 유지되고 transport 결합만 줄어든다.

## Phase 3. BrowserPane 역할 재정의

### 목표

- [x] `BrowserPane`를 스크린샷 렌더러에서 live browser surface host/controller로 바꾼다.

### 현재 문제

- [x] `web/src/components/BrowserPane.tsx`가 `img` 기반 preview만 제공한다.
- [x] wrapper `focus()`만 가능하고 실제 browser focus handoff가 불가능하다.

### 새 역할 체크리스트

- [x] BrowserPane이 live browser surface가 배치될 container를 선언한다.
- [x] BrowserPane이 shell에 container bounds를 전달할 수 있게 한다.
- [x] BrowserPane이 browser focus 상태를 시각적으로 표시한다.
- [x] BrowserPane이 live mode / inspection mode를 구분한다.
- [x] live surface unavailable 시에만 screenshot fallback을 노출한다.
- [x] live browser surface와 historical step preview를 분리한다.
- [ ] `Step preview`를 BrowserPane primary mode가 아닌 별도 inspector/drawer/modal/sidebar detail로 옮길지 결정한다.

### 수정 대상

- [x] `web/src/components/BrowserPane.tsx`
- [x] `web/src/App.tsx`
- [x] `web/src/reviewPanel.ts`
- [ ] 필요 시 `web/src/components/StepInspector.tsx` 추가

### 완료 기준

- [x] BrowserPane이 더 이상 단순 screenshot viewer가 아니게 된다.
- [x] live browser surface UX와 historical preview UX가 서로 충돌하지 않게 된다.

## Phase 4. FocusManager 및 단축키 설계

### 목표

- [x] side panel / browser surface / chat input 사이를 앱 레벨에서 일관되게 이동한다.

### 신규 후보 파일

- [x] `web/src/focus/focusManager.ts`
- [ ] `web/src/focus/FocusProvider.tsx`
- [ ] 또는 shell 측 focus bridge 모듈

### 정의할 focus region

- [x] `browser-surface`
- [x] `verification-sidebar`
- [x] `chat-input`

### 체크리스트

- [x] `focusBrowserSurface()`를 정의한다.
- [x] `focusVerificationSidebar()`를 정의한다.
- [x] `focusChatInput()`를 정의한다.
- [ ] 마지막 두 영역 간 토글 동작을 정의한다.
- [x] 포커스 변경 이벤트를 UI state에 반영한다.
- [x] global shortcut 후보를 정한다.
- [x] browser focus가 DOM wrapper가 아니라 shell/native surface로 전달되도록 한다.
- [x] sidebar/chat은 React DOM focus로 처리한다.
- [x] `VerificationSidebar`의 기존 버튼 기반 포커스 이동을 FocusManager 기반으로 바꾼다.
- [x] `ChatPanel`이 chat input ref 또는 focus target을 노출하게 한다.

### 영향 파일

- [x] `web/src/App.tsx`
- [x] `web/src/components/VerificationSidebar.tsx`
- [x] `web/src/components/ChatPanel.tsx`
- [x] `web/src/components/BrowserPane.tsx`

### 완료 기준

- [x] 사용자 단축키로 browser/sidebar/chat 사이 이동할 수 있다.
- [x] browser surface focus가 실제 interactive surface에 적용된다.

## Phase 5. Artifact 접근 방식 재설계

### 목표

- [x] artifact를 `/api/sessions/.../artifacts/...` URL이 아니라 bridge API로 다룬다.

### 새 bridge API 후보

- [x] `readArtifactText(sessionId, name)`
- [x] `readArtifactBinary(sessionId, name)`
- [x] `openArtifact(sessionId, name)`
- [ ] `resolveArtifactHandle(sessionId, name)`

### 체크리스트

- [x] `artifacts_base_url` 제거 또는 축소 방향을 확정한다.
- [x] `buildArtifactUrl()` 중심 흐름을 제거한다.
- [x] `web/src/components/ArtifactLinks.tsx`를 bridge 기반 open/read 방식으로 바꾼다.
- [x] `web/src/components/ProcessHistorySection.tsx`를 bridge 기반 artifact 접근으로 바꾼다.
- [x] `web/src/components/ConfirmationNeededSection.tsx`를 bridge 기반 artifact 접근으로 바꾼다.
- [x] `web/src/components/AccessibilityTreeView.tsx`의 `fetch(artifactUrl)`를 제거한다.
- [x] `src/ui/session_controller.py`에서 HTTP URL 기반 artifact 모델을 정리한다.
- [x] `src/ui/models.py`에서 artifact field 구조를 desktop bridge 친화적으로 정리한다.

### 영향 파일

- [x] `web/src/reviewPanel.ts`
- [x] `web/src/components/BrowserPane.tsx`
- [x] `web/src/components/ArtifactLinks.tsx`
- [x] `web/src/components/ProcessHistorySection.tsx`
- [x] `web/src/components/ConfirmationNeededSection.tsx`
- [x] `web/src/components/AccessibilityTreeView.tsx`
- [x] `src/ui/session_controller.py`
- [x] `src/ui/models.py`

### 완료 기준

- [x] 프론트엔드가 artifact URL 문자열 조합 없이 동작한다.
- [x] live screenshot과 historical artifact 접근 경로가 분리된다.

## Phase 6. Desktop bridge 연결

### 목표

- [x] React 앱과 Python runtime 사이를 desktop IPC로 연결한다.

### 체크리스트

- [x] shell에서 `SessionClient` contract를 구현한다.
- [x] shell에서 browser surface host를 관리한다.
- [x] BrowserPane가 shell에 자신의 bounds/focus intent를 전달한다.
- [x] Python service 호출 결과를 기존 TS 상태 모델과 최대한 동일한 shape로 유지한다.
- [x] polling 기반 snapshot/steps/verification 흐름이 desktop bridge에서도 동작하도록 만든다.
- [x] bridge 오류를 UI에서 구조적으로 표시할 수 있게 한다.

### 주의사항

- [x] 1차는 polling 유지
- [ ] 성능 문제가 드러날 때만 push/subscription으로 확장

### 완료 기준

- [x] HTTP 없이 desktop bridge만으로 세션 생성/실행/중지/메시지 전송이 가능하다.
- [x] BrowserPane live surface와 Python 코어가 bridge를 통해 연결된다.

## Phase 7. HTTP 제거

### 목표

- [x] desktop bridge가 안정화되면 FastAPI layer를 제거한다.

### 체크리스트

- [x] `src/ui/server.py` 제거
- [x] `src/ui/routes/sessions.py` 제거
- [x] `src/ui/models.py` 하단 HTTP DTO (`CreateSessionResponse`, `StartSessionRequest`, `SendMessageRequest`) 정리
- [x] desktop 전용 bootstrap 경로 정리
- [x] `main.py --ui`와 desktop launcher 관계 재정리

### 완료 기준

- [x] desktop app 경로에서 FastAPI/uvicorn/CORS 없이 동일 기능이 동작한다.

## 테스트 / 검증 체크리스트

### Python

- [x] `SessionService` 단위 테스트 추가
- [x] `SessionController` 기존 테스트 유지 또는 보강
- [x] artifact bridge 관련 테스트 추가
- [ ] 기존 HTTP parity 단계에서는 기존 UI 테스트가 깨지지 않도록 유지

### Frontend

- [x] `SessionClient` abstraction 테스트 추가
- [x] BrowserPane live/fallback 모드 테스트 추가
- [x] FocusManager 단위 테스트 추가
- [x] keyboard shortcut 동작 테스트 추가
- [x] artifact bridge consumer 컴포넌트 테스트 갱신

### Integration

- [x] desktop bridge <-> Python service 연동 테스트 추가
- [x] browser surface focus handoff 검증
- [x] sidebar <-> chat <-> browser 포커스 전환 검증

## 리스크 체크리스트

### 리스크 1. interactive browser surface 호스팅 난이도

- [x] `PlaywrightComputer` 유지로 충분한지 검증한다.
- [ ] 필요하면 새 backend (`DesktopBrowserComputer`) 도입을 허용한다.

### 리스크 2. BrowserPane와 step preview 역할 충돌

- [x] live surface와 historical preview를 분리하는 UX를 우선 적용한다.

### 리스크 3. polling over IPC 비용

- [x] 1차는 유지하되 병목 측정을 준비한다.

### 리스크 4. stop 동작의 비즉시성

- [x] stop pending 상태를 UX에서 명확히 표시한다.
- [ ] 추후 stronger cancellation 필요성을 평가한다.

## 최종 완료 기준

- [x] React 앱이 HTTP 없이 desktop bridge를 통해 세션을 생성/시작/정지/메시지 전송할 수 있다.
- [x] BrowserPane이 live browser surface의 실제 host/controller 역할을 한다.
- [x] sidebar / chat / browser surface 사이 포커스를 단축키와 명시적 focus action으로 이동할 수 있다.
- [x] artifact 접근이 `artifacts_base_url` 없이 동작한다.
- [x] `SessionController` 중심의 런타임 코어가 유지된다.
- [x] FastAPI layer를 제거해도 동일한 세션 기능이 동작한다.

## 권장 구현 순서

- [x] Commit A: service 추출 + HTTP parity 유지
- [x] Commit B: frontend client abstraction
- [x] Commit C: BrowserPane/live surface 구조 변경
- [x] Commit D: focus manager + shortcut
- [x] Commit E: artifact bridge
- [x] Commit F: desktop bridge cutover + FastAPI 제거
