# FastAPI + React 기반 실시간 screenshot/state stream UI 구현 체크리스트

## 0. 최종 방향

- [ ] **live preview는 `webm`이 아니라 screenshot/state stream으로 구현한다.**
- [ ] `webm`과 `logs/history/*`는 계속 **recording / replay / debug artifact** 용도로 유지한다.
- [ ] Playwright browser lifecycle ownership은 계속 `PlaywrightComputer`가 가진다.
- [ ] React UI는 browser/page 객체를 직접 만지지 않고 **FastAPI가 제공하는 session snapshot**만 소비한다.
- [ ] 첫 버전은 **FastAPI + React(Vite) + polling** 기준으로 구현한다.
- [ ] websocket은 1차 범위에서 제외하고, 필요하면 2차로 SSE를 붙인다.

---

## 1. 목표 / 성공 기준

- [ ] 사용자가 로컬 UI에서 세션을 만들고 agent를 시작할 수 있다.
- [ ] 사용자가 채팅 입력창에 query/message를 보낼 수 있다.
- [ ] 브라우저 preview pane에서 최신 screenshot과 URL을 거의 실시간으로 볼 수 있다.
- [ ] sidebar에서 최신 reasoning, 최근 action, step timeline을 볼 수 있다.
- [ ] 세션 완료 후 `webm` 및 `logs/history/*.png|*.html|*.json` 링크를 확인할 수 있다.
- [ ] 기존 CLI 모드(`python main.py --query ...`)는 그대로 동작한다.

---

## 2. 왜 이 구조가 맞는가

- [ ] 현재 `main.py`는 `PlaywrightComputer` + `BrowserAgent`를 생성하고 `agent.agent_loop()`를 실행한다.
- [ ] 현재 `BrowserAgent.run_one_iteration()`가 가장 자연스러운 **step 경계**다.
- [ ] 현재 `PlaywrightComputer.current_state()`가 `EnvState(screenshot, url)`를 만든다.
- [ ] 현재 `_write_history_snapshot()`가 step별 artifact를 이미 남긴다.
- [ ] 따라서 가장 적은 변경으로 갈 수 있는 구조는:
  - [ ] `BrowserAgent`와 `PlaywrightComputer` 위에 `SessionController`를 추가하고
  - [ ] FastAPI가 그 상태를 API로 노출하고
  - [ ] React가 polling으로 읽는 방식이다.

---

## 3. 범위 / 비범위

### In scope

- [ ] FastAPI 기반 로컬 UI backend 추가
- [ ] React + Vite 기반 로컬 UI frontend 추가
- [ ] screenshot/state polling 기반 browser preview 추가
- [ ] chat sidebar 추가
- [ ] step timeline 추가
- [ ] session lifecycle API 추가
- [ ] 기존 Playwright logging/video artifact 재사용

### Out of scope (1차)

- [ ] 실제 DOM을 직접 클릭하는 embedded live browser surface
- [ ] multi-user / auth / remote deployment
- [ ] websocket-first architecture
- [ ] Browserbase 중심 재설계
- [ ] agent core behavior 리팩터링

---

## 4. 목표 아키텍처

```text
User
  -> React UI (browser preview + chat sidebar)
  -> FastAPI server
  -> SessionController
  -> BrowserAgent.run_one_iteration()
  -> PlaywrightComputer
  -> Chromium
```

### 역할 분리

#### React UI
- [ ] browser preview pane 렌더링
- [ ] chat 입력/전송
- [ ] session status 표시
- [ ] latest reasoning / actions 표시
- [ ] step timeline 표시
- [ ] artifact 링크 표시

#### FastAPI server
- [ ] session 생성/종료 API 제공
- [ ] snapshot 조회 API 제공
- [ ] step history 조회 API 제공
- [ ] message enqueue API 제공
- [ ] artifact 파일 서빙
- [ ] CORS 및 dev proxy 대응

#### SessionController
- [ ] `BrowserAgent` + `PlaywrightComputer` 조립
- [ ] worker thread에서 agent 실행
- [ ] 최신 snapshot cache 유지
- [ ] step records 유지
- [ ] user messages queue 처리
- [ ] run/stop/error 상태 전이 관리

#### BrowserAgent
- [ ] 기존 모델 호출/도구 호출 흐름 유지
- [ ] step 단위 이벤트를 외부로 emit 가능하게 확장

#### PlaywrightComputer
- [ ] browser/context/page lifecycle 유지
- [ ] 현재 screenshot/url 생성 유지
- [ ] 현재 history/video artifact 기록 유지

---

## 5. 권장 디렉토리 구조

```text
src/
  ui/
    __init__.py
    models.py
    session_controller.py
    session_store.py
    serializers.py
    server.py
    routes/
      __init__.py
      sessions.py

web/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts
    hooks/
      useSessionSnapshot.ts
      useSessionSteps.ts
      useSendMessage.ts
    components/
      Layout.tsx
      BrowserPane.tsx
      ChatPanel.tsx
      StepTimeline.tsx
      StatusBar.tsx
      ArtifactLinks.tsx
    types/
      api.ts
    styles/
      app.css
```

- [ ] Python UI 코드는 `src/ui/` 아래에 모은다.
- [ ] React 앱은 `web/` 디렉토리로 분리한다.
- [ ] 기존 runtime code(`src/agent.py`, `src/computers/...`)는 가능한 최소 수정만 한다.

---

## 6. 백엔드 모델 체크리스트 (`src/ui/models.py`)

### `SessionStatus`

- [ ] `idle`
- [ ] `running`
- [ ] `waiting_for_input`
- [ ] `complete`
- [ ] `error`
- [ ] `stopped`

### `StepAction`

- [ ] `name: str`
- [ ] `args: dict[str, Any]`

### `StepRecord`

- [ ] `step_id: int`
- [ ] `timestamp: float`
- [ ] `reasoning: str | None`
- [ ] `function_calls: list[StepAction]`
- [ ] `url: str | None`
- [ ] `status: Literal["running", "complete", "error"]`
- [ ] `screenshot_path: str | None`
- [ ] `html_path: str | None`
- [ ] `metadata_path: str | None`
- [ ] `error_message: str | None`

### `ChatMessage`

- [ ] `id: str`
- [ ] `role: Literal["user", "assistant", "system"]`
- [ ] `text: str`
- [ ] `timestamp: float`

### `SessionSnapshot`

- [ ] `session_id: str`
- [ ] `status: SessionStatus`
- [ ] `current_url: str | None`
- [ ] `latest_screenshot_b64: str | None`
- [ ] `latest_step_id: int | None`
- [ ] `last_reasoning: str | None`
- [ ] `last_actions: list[StepAction]`
- [ ] `messages: list[ChatMessage]`
- [ ] `final_reasoning: str | None`
- [ ] `error_message: str | None`
- [ ] `artifacts_base_url: str | None`
- [ ] `updated_at: float`

---

## 7. `BrowserAgent` 변경 체크리스트 (`src/agent.py`)

### 목표

- [ ] agent core behavior는 유지한다.
- [ ] UI가 읽을 수 있는 step-level event만 추가한다.

### 변경 항목

- [ ] `BrowserAgent.__init__()`에 선택적 event sink / callback 인자 추가
- [ ] `append_user_message(text: str)` public method 추가
- [ ] `get_recent_messages(limit: int)` public method 추가
- [ ] `run_one_iteration()` 내부에서 step 이벤트 수집
  - [ ] model response 수신 직후
  - [ ] reasoning 추출 직후
  - [ ] function calls 추출 직후
  - [ ] action 실행 완료 직후
  - [ ] final complete/error 시점
- [ ] `final_reasoning`을 snapshot에 반영할 수 있게 전달

### 하지 말 것

- [ ] `_contents`를 UI가 직접 조작하게 만들지 않는다.
- [ ] model/tool behavior를 바꾸지 않는다.
- [ ] screenshot trimming 정책을 UI 때문에 깨지 않게 한다.

---

## 8. `PlaywrightComputer` 변경 체크리스트 (`src/computers/playwright/playwright.py`)

### 유지할 것

- [ ] `current_state() -> EnvState` 계약 유지
- [ ] `record_video_dir` 기반 `webm` 저장 유지
- [ ] `_write_history_snapshot()` 유지

### 보강할 것

- [ ] latest artifact 경로를 controller가 읽을 수 있는 최소한의 접근점 추가 검토
- [ ] step metadata에 UI에서 유용한 필드 추가 검토
  - [ ] `step`
  - [ ] `timestamp`
  - [ ] `url`
  - [ ] `html_path`
  - [ ] `screenshot_path`
  - [ ] 필요 시 `status`

### 주의

- [ ] UI polling 요청마다 `current_state()`를 새로 호출하지 않는다.
- [ ] preview는 agent step 완료 시점의 cached screenshot을 사용한다.

---

## 9. SessionController 체크리스트 (`src/ui/session_controller.py`)

### 책임

- [ ] session 생성
- [ ] session 시작
- [ ] session 중지
- [ ] worker thread 실행
- [ ] snapshot cache 갱신
- [ ] step timeline 보관
- [ ] message queue 처리

### 내부 상태

- [ ] `session_id`
- [ ] `status`
- [ ] `latest_snapshot`
- [ ] `steps`
- [ ] `messages`
- [ ] `stop_requested`
- [ ] `lock`
- [ ] `thread`

### public API

- [ ] `start()`
- [ ] `stop()`
- [ ] `enqueue_message(text: str)`
- [ ] `get_snapshot()`
- [ ] `get_steps()`
- [ ] `get_artifact_path(name: str)`

### 구현 규칙

- [ ] agent는 worker thread에서 실행
- [ ] UI thread/request는 controller cache만 읽음
- [ ] session state update는 lock으로 보호
- [ ] stop 요청 시 안전하게 종료 상태 전이

---

## 10. SessionStore 체크리스트 (`src/ui/session_store.py`)

- [ ] active sessions를 메모리에서 관리한다.
- [ ] `create_session()` 제공
- [ ] `get_session(session_id)` 제공
- [ ] `delete_session(session_id)` 제공
- [ ] 필요 시 단일 세션 MVP라도 store abstraction은 미리 만든다.

---

## 11. FastAPI 서버 체크리스트 (`src/ui/server.py`, `src/ui/routes/sessions.py`)

### 의존성

- [ ] `fastapi` 추가
- [ ] `uvicorn` 추가
- [ ] 필요 시 `python-multipart` 여부 검토

### 앱 구성

- [ ] `FastAPI()` 앱 생성
- [ ] health endpoint 추가
- [ ] sessions router 등록
- [ ] CORS 설정 추가
  - [ ] React dev server origin 허용

### API 엔드포인트

#### `POST /api/sessions`
- [ ] 새 session 생성
- [ ] response: `session_id`, initial snapshot

#### `POST /api/sessions/{session_id}/start`
- [ ] session 시작
- [ ] 최초 query 전달 방식 확정

#### `POST /api/sessions/{session_id}/messages`
- [ ] user message enqueue
- [ ] request body: `{ "text": "..." }`

#### `POST /api/sessions/{session_id}/stop`
- [ ] 안전한 stop 요청

#### `GET /api/sessions/{session_id}`
- [ ] `SessionSnapshot` 반환

#### `GET /api/sessions/{session_id}/steps`
- [ ] `StepRecord[]` 반환
- [ ] 필요 시 `after_step_id` query param 지원

#### `GET /api/sessions/{session_id}/artifacts/{name}`
- [ ] png/html/json/webm 파일 제공

#### `GET /api/health`
- [ ] 서버 상태 반환

### 2차 옵션

- [ ] `GET /api/sessions/{session_id}/events` SSE endpoint 검토

---

## 12. API 계약 체크리스트

### Session create response 예시

```json
{
  "session_id": "ses_123",
  "snapshot": {
    "session_id": "ses_123",
    "status": "idle",
    "current_url": null,
    "latest_screenshot_b64": null,
    "latest_step_id": null,
    "last_reasoning": null,
    "last_actions": [],
    "messages": [],
    "final_reasoning": null,
    "error_message": null,
    "artifacts_base_url": "/api/sessions/ses_123/artifacts",
    "updated_at": 0
  }
}
```

- [ ] 위 형태를 기준 계약으로 확정한다.

### Message request 예시

```json
{
  "text": "Go to example.com and summarize the page"
}
```

- [ ] message API는 단순 text contract로 시작한다.

### Steps response 예시

```json
[
  {
    "step_id": 1,
    "timestamp": 1710000000.0,
    "reasoning": "I should open the browser first.",
    "function_calls": [
      {"name": "open_web_browser", "args": {}}
    ],
    "url": "https://www.google.com",
    "status": "complete",
    "screenshot_path": "step-0001.png",
    "html_path": "step-0001.html",
    "metadata_path": "step-0001.json",
    "error_message": null
  }
]
```

- [ ] step API는 timeline 렌더링에 필요한 필드를 모두 포함한다.

---

## 13. React 앱 체크리스트 (`web/`)

### 스택

- [ ] React
- [ ] Vite
- [ ] TypeScript
- [ ] fetch 기반 API client
- [ ] 상태관리는 React state + custom hooks로 시작

### 의존성

- [ ] `react`
- [ ] `react-dom`
- [ ] `typescript`
- [ ] `vite`
- [ ] `@types/react`
- [ ] `@types/react-dom`

### 기본 레이아웃

- [ ] 좌측 또는 우측에 chat/sidebar
- [ ] 반대편에 browser preview pane
- [ ] 상단 status bar
- [ ] 하단 input composer

### 컴포넌트

#### `App.tsx`
- [ ] 전체 session 화면 조립

#### `Layout.tsx`
- [ ] 2-column split layout

#### `StatusBar.tsx`
- [ ] session status
- [ ] current URL
- [ ] latest step id
- [ ] start/stop button

#### `BrowserPane.tsx`
- [ ] latest screenshot 표시
- [ ] loading/empty/error 상태 처리
- [ ] preview 갱신 시간 표시

#### `ChatPanel.tsx`
- [ ] message list
- [ ] text input
- [ ] send button
- [ ] enter submit

#### `StepTimeline.tsx`
- [ ] step 목록 표시
- [ ] reasoning 표시
- [ ] action 목록 표시
- [ ] step status 표시

#### `ArtifactLinks.tsx`
- [ ] latest png/html/json 링크
- [ ] session 완료 후 webm 링크

---

## 14. React hooks 체크리스트

### `useSessionSnapshot(sessionId)`

- [ ] `GET /api/sessions/{id}` polling
- [ ] 기본 polling 주기 300~500ms
- [ ] status가 `complete`/`error`이면 polling 간격 완화 또는 중지

### `useSessionSteps(sessionId)`

- [ ] `GET /api/sessions/{id}/steps` polling
- [ ] 필요 시 `after_step_id` 기반 incremental fetch

### `useSendMessage(sessionId)`

- [ ] `POST /api/sessions/{id}/messages`
- [ ] optimistic clear / disabled state 처리

### `useSessionControls(sessionId)`

- [ ] start 호출
- [ ] stop 호출

---

## 15. React 상태 관리 규칙

- [ ] 서버 상태는 custom hook에서 관리한다.
- [ ] layout state만 component local state로 둔다.
- [ ] `SessionSnapshot`와 `StepRecord` 타입은 API contract와 1:1로 맞춘다.
- [ ] 중복 파생 상태를 최소화한다.

---

## 16. Vite / 개발 환경 체크리스트

- [ ] `web/package.json` 생성
- [ ] `vite.config.ts`에서 FastAPI dev proxy 설정
  - [ ] `/api` -> `http://127.0.0.1:<fastapi-port>`
- [ ] 개발 커맨드 문서화
  - [ ] backend: `uv run python main.py --ui`
  - [ ] frontend: `npm run dev`

---

## 17. `main.py` 변경 체크리스트

- [ ] 기존 CLI 진입점 유지
- [ ] `--ui` 플래그 추가
- [ ] UI 모드일 때 FastAPI server bootstrap 실행
- [ ] CLI 모드와 UI 모드가 공존하도록 분기
- [ ] 필요 시 UI용 port/config 인자 추가

예시:

- [ ] `python main.py --query "..."` -> 기존 CLI
- [ ] `python main.py --ui` -> FastAPI server

---

## 18. 구현 순서 체크리스트

### Phase 1. 모델 / 계약 고정

- [ ] `SessionStatus`, `StepAction`, `StepRecord`, `ChatMessage`, `SessionSnapshot` 정의
- [ ] API request/response schema 정의
- [ ] screenshot base64 serializer 추가

완료 기준:

- [ ] FastAPI와 React가 같은 계약으로 개발 가능하다.

### Phase 2. Agent 이벤트 추출

- [ ] `BrowserAgent`에 event sink 추가
- [ ] `run_one_iteration()`에서 reasoning / function call / result 이벤트 수집
- [ ] final/error 상태를 snapshot으로 반영

완료 기준:

- [ ] step record를 생성할 수 있다.

### Phase 3. SessionController / SessionStore 구현

- [ ] session lifecycle 구현
- [ ] worker thread 구현
- [ ] latest snapshot cache 구현
- [ ] step history 축적 구현
- [ ] message queue 구현

완료 기준:

- [ ] UI 없이도 Python만으로 세션 상태를 읽을 수 있다.

### Phase 4. FastAPI API 구현

- [ ] sessions router 구현
- [ ] health endpoint 구현
- [ ] artifact file serving 구현
- [ ] CORS/proxy 확인

완료 기준:

- [ ] curl로 session create/start/message/stop/get 가능하다.

### Phase 5. React UI MVP 구현

- [ ] Vite 앱 scaffold
- [ ] API client 구현
- [ ] hooks 구현
- [ ] split layout 구현
- [ ] browser pane 구현
- [ ] chat panel 구현
- [ ] step timeline 구현
- [ ] artifact links 구현

완료 기준:

- [ ] side-by-side UI로 agent 상태를 실시간 확인할 수 있다.

### Phase 6. polish / 2차 확장

- [ ] polling 최적화
- [ ] SSE 실험 여부 검토
- [ ] replay UX 개선
- [ ] README/사용법 문서화

완료 기준:

- [ ] 개발자와 사용자가 UI 모드를 쉽게 실행할 수 있다.

---

## 19. 테스트 체크리스트

### Python 단위 테스트

- [ ] `SessionSnapshot` / `StepRecord` 직렬화 테스트
- [ ] `SessionController` 상태 전이 테스트
- [ ] stop/start behavior 테스트
- [ ] screenshot cache 업데이트 테스트

### Python 통합 테스트

- [ ] session create -> start -> poll -> complete 흐름 테스트
- [ ] step history 누적 테스트
- [ ] artifact endpoint 응답 테스트

### React 테스트

- [ ] snapshot polling hook 테스트
- [ ] steps polling hook 테스트
- [ ] chat submit flow 테스트
- [ ] loading/error/empty UI 상태 테스트

### 회귀 테스트

- [ ] `tests/test_main.py` 유지
- [ ] `tests/test_agent.py` 유지
- [ ] `tests/test_playwright_logging.py` 유지
- [ ] 기존 CLI 실행이 깨지지 않음을 확인

---

## 20. 의존성 변경 체크리스트

### `pyproject.toml`

- [ ] `fastapi` 추가
- [ ] `uvicorn` 추가

### `web/package.json`

- [ ] React/Vite/TypeScript 의존성 추가

### 문서

- [ ] README에 UI 실행 방법 추가
- [ ] `--log`가 민감 정보를 저장할 수 있다는 경고를 UI 모드에도 반영

---

## 21. 리스크 / 대응 체크리스트

### 리스크 1. polling이 Playwright에 부하를 줌

- [ ] polling은 FastAPI cache만 읽게 한다.
- [ ] screenshot 생성은 agent step 완료 시점에만 한다.

### 리스크 2. agent가 blocking이라 UI 응답성이 떨어짐

- [ ] worker thread로 격리한다.
- [ ] FastAPI request path는 agent 본체를 직접 기다리지 않는다.

### 리스크 3. `_contents`에 강결합될 수 있음

- [ ] public adapter method만 노출한다.
- [ ] UI는 agent internals 대신 snapshot API만 본다.

### 리스크 4. 민감 정보가 screenshot/html/video에 남음

- [ ] artifact 저장은 opt-in으로 유지한다.
- [ ] UI 문서와 화면에 경고를 넣는다.

---

## 22. 최종 요약 체크리스트

- [ ] **Backend는 FastAPI + SessionController 중심으로 간다.**
- [ ] **Frontend는 React + Vite + polling hooks 중심으로 간다.**
- [ ] **live preview는 screenshot/state stream이다.**
- [ ] **recording은 기존 webm이다.**
- [ ] **replay/debug는 기존 history png/html/json을 재사용한다.**
- [ ] **1차 목표는 side-by-side local UI MVP 완성이다.**

---

## 23. 바로 다음 액션

- [ ] `pyproject.toml`에 FastAPI/uvicorn 추가
- [ ] `src/ui/models.py`부터 만들기
- [ ] `BrowserAgent`에 event sink 추가
- [ ] `SessionController` 구현
- [ ] FastAPI sessions API 구현
- [ ] `web/` React 앱 scaffold
- [ ] `BrowserPane`, `ChatPanel`, `StepTimeline` 구현
