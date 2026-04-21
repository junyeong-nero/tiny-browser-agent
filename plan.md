# Planner Agent + ARIA Grounding 도입 계획

## 목표
1. `BrowserAgent` 앞단에 **Planner Agent** 를 두어 query → subgoal list 로 분해한 뒤 actor 에 순차 공급.
2. 페이지 grounding 방식을 CLI 에서 선택: `--grounding {vision,text,mixed}` (기본 `vision`, 현재 동작 유지).
   - `vision`: 지금처럼 screenshot + 좌표 tool.
   - `text`: ARIA snapshot + ref 기반 semantic tool.
   - `mixed`: 둘 다 context 에 포함, 두 tool 세트 모두 노출.

## 비목표 (이번 범위 밖)
- Retriever/Verifier agent 분리
- Trajectory cache / `learn()` 구현
- Selenium/Appium 지원

---

## Phase 0 — 설계 확정
- [ ] Grounding mode 타입 정의 (`Literal["vision", "text", "mixed"]`) — `src/agents/types.py` 신설 또는 `actor_agent.py` 상단
- [ ] Semantic tool 네이밍 규약 확정: `click_by_ref`, `type_by_ref`, `hover_by_ref`, `scroll_by_ref`
- [ ] ARIA ref 형식 결정: `[12]` 스타일 정수 id 재할당 (snapshot 시점마다 재매핑)
- [ ] Planner 출력 스키마 확정: `{"subgoals": [{"id": int, "description": str, "success_criteria": str}]}`

---

## Phase 1 — ARIA Snapshot 인프라
- [ ] `PlaywrightBrowser.aria_snapshot() -> AriaSnapshot` 추가 (`src/browser/playwright.py`)
  - [ ] `page.accessibility.snapshot(interesting_only=True)` 호출
  - [ ] 트리 순회하며 각 노드에 정수 `ref` 부여, `ref → locator resolver` 맵 내부 저장
  - [ ] 텍스트 직렬화: `[ref] role "name" [state]` 한 줄씩
- [ ] `AriaSnapshot` pydantic 모델: `{text: str, ref_map: dict[int, NodeInfo], url: str}`
- [ ] `PlaywrightBrowser.resolve_ref(ref) -> Locator` 구현 (role+name+nth 기반 locator 재구성)
- [ ] 스크린샷 1회 찍을 때 ARIA snapshot 도 함께 캐시 (중복 DOM 접근 방지)
- [ ] 단위 테스트: fixture HTML → snapshot text / ref resolution 왕복 검증 (`tests/test_aria_snapshot.py`)

---

## Phase 2 — Semantic Tool 집합
- [ ] `src/tools/click_by_ref.py` — `(ref: int)` → `browser.resolve_ref(ref).click()`
- [ ] `src/tools/type_by_ref.py` — `(ref: int, text: str, press_enter: bool = False)`
- [ ] `src/tools/hover_by_ref.py`
- [ ] `src/tools/scroll_by_ref.py` — `(ref: int, direction: Literal["up","down"])`
- [ ] ref 없이 쓰는 tool (navigate, go_back, go_forward, key_combination, wait, search) 은 **양쪽 모드 공용**으로 유지
- [ ] `ref` 가 stale 일 때 에러 메시지: "ref 12 is stale, request a new snapshot"
- [ ] 단위 테스트: 각 tool 의 happy path + stale ref 실패 (`tests/test_semantic_tools.py`)

---

## Phase 3 — Tool Executor & Context 분기
- [ ] `BrowserToolExecutor.__init__` 에 `grounding: GroundingMode` 파라미터 추가 (`src/tool_executor.py`)
- [ ] `build_tools()` 에서 grounding 별로 노출 tool 필터:
  - [ ] `vision`: 좌표 tool + 공용 tool
  - [ ] `text`: ref tool + 공용 tool
  - [ ] `mixed`: 전부
- [ ] Function response 조립 시 context 주입 분기:
  - [ ] `vision`: screenshot part (현행)
  - [ ] `text`: ARIA text part (screenshot 제외)
  - [ ] `mixed`: 둘 다
- [ ] `prune_old_screenshot_parts` 와 동일한 `prune_old_aria_parts` 추가 (text 모드에서도 컨텍스트 폭주 방지, 기본 최근 3턴)

---

## Phase 4 — Planner Agent
- [ ] `src/agents/planner_agent.py` 신설
  - [ ] `PlannerAgent(query, llm_client, model_name)` 클래스
  - [ ] `plan() -> list[Subgoal]` — 단일 LLM 호출, JSON 스키마 강제
  - [ ] `replan(current_subgoal, failure_reason, remaining) -> list[Subgoal]` — actor 가 중도 실패 시 호출
  - [ ] 시스템 프롬프트: 브라우저 agent 가 수행 가능한 action 의 범주를 간략히 설명, 너무 세분화하지 않도록 지시
- [ ] `Subgoal` dataclass: `id`, `description`, `success_criteria`, `status Literal["pending","active","done","failed"]`
- [ ] 테스트: mocked LLM 으로 스키마 준수/파싱 실패 재시도 (`tests/test_planner_agent.py`)

---

## Phase 5 — BrowserAgent 와 Planner 연동
- [ ] `BrowserAgent.__init__` 에 `subgoals: list[Subgoal] | None = None` 파라미터 추가
- [ ] `agent_loop()` 변경:
  - [ ] subgoals 있으면 각 subgoal 을 새로운 `_contents` seed 로 actor 루프 실행
  - [ ] 각 subgoal 시작 시 `append_user_message(f"[Subgoal {i}] {description}\nSuccess: {success_criteria}")`
  - [ ] 실패/타임아웃 시 `PlannerAgent.replan()` 호출 여부 결정 (최초엔 실패 시 전체 중단 → 추후 replan 확장)
- [ ] `_emit_event("subgoal_started" | "subgoal_completed" | "subgoal_failed", ...)` 추가
- [ ] UI server 이벤트 스트림에 subgoal 표시 확인 (`src/ui/server.py` 영향도 체크)

---

## Phase 6 — CLI 통합
- [ ] `main.py` 에 `--grounding` 추가 (`choices=["vision","text","mixed"]`, default `"vision"`)
- [ ] `main.py` 에 `--planner` flag 추가 (default `False`; planner 를 opt-in 으로 시작)
- [ ] `BrowserAgent` 생성 시 grounding 전달
- [ ] `--planner` 이면 `PlannerAgent.plan()` 먼저 호출 → 결과를 `BrowserAgent` 에 주입
- [ ] `text` 모드 x Gemini Computer Use 호환성 확인: 좌표 tool 을 선언 안 하면 computer use 모드가 작동 안 할 가능성 — 필요 시 `text` 모드는 일반 function-calling 모델 (`--model` 다른 기본값) 로 fallback 하는 분기 설계
- [ ] `AGENTS.md` / `README.md` 업데이트 (flag 설명, grounding 모드 비교 표)

---

## Phase 7 — 검증
- [ ] 통합 테스트: 세 grounding 모드 각각으로 동일 fixture 페이지에서 "검색창에 'hello' 입력" 시나리오 성공
- [ ] 기존 회귀 테스트 (`uv run pytest`) 전부 통과
- [ ] 수동 smoke: `uv run main.py "summarize example.com" --grounding text --initial_url https://example.com`
- [ ] 수동 smoke: `uv run main.py "<multi-step query>" --planner --grounding mixed --log` → `logs/history/.../actions.jsonl` 에 subgoal 경계 기록 확인

---

## 열린 질문 (진행 중 결정)
- [ ] `text` 모드에서 Gemini Computer Use 전용 모델을 그대로 쓸 수 있는지, 아니면 일반 Gemini function-calling 모델로 스위치해야 하는지
- [ ] ARIA snapshot 을 매 action 후 새로 뽑을지 / LLM 이 명시적으로 `refresh_snapshot()` 호출하도록 할지 (토큰 비용 trade-off)
- [ ] `mixed` 모드 기본값 채택 여부 — 정확도는 오르지만 비용 2배 이상
