# BrowserState 계층화 및 UI Graph Visualization 리팩토링 계획

## 목표

`EnvState(screenshot, url)` 중심의 평면 상태 모델을 다음 계층 구조로 확장한다.

```text
BrowserState
├── PageState
├── ViewportState
└── InteractionState
```

그리고 기존 UI의 D3 기반 navigation graph를 유지하면서, `BrowserState` 계층을 별도의 graph/tree view로 시각화할 수 있게 만든다.

## 핵심 원칙

- 기존 tool/agent 동작을 깨지 않는다.
- `EnvState` import와 `state.url`, `state.screenshot` 접근은 migration 기간 동안 계속 지원한다.
- D3 구현은 버리지 않고 재사용하되, navigation trajectory graph와 BrowserState graph의 책임을 분리한다.
- 처음부터 큰 UI 개편을 하지 않고, backend state model → artifact metadata → UI graph 순서로 작게 진행한다.
- 각 phase마다 테스트를 추가/수정하고 기존 테스트를 통과시킨다.

---

## Phase 0 — 현재 동작 고정 및 리팩토링 경계 설정

- [x] `EnvState` 생성/소비 지점을 재확인한다.
  - [x] `src/browser/playwright.py`
  - [x] `src/browser/actions.py`
  - [x] `src/tools/*`
  - [x] `src/agents/actor_agent.py`
  - [x] `tests/test_agent.py`
  - [x] `tests/test_tool_calling.py`
  - [x] `tests/test_playwright_logging.py`
- [x] 기존 public contract를 명시한다.
  - [x] browser action은 상태 객체를 반환한다.
  - [x] 상태 객체는 최소 `url`과 `screenshot`을 제공한다.
  - [x] logging enabled 시 `history/step-XXXX.{png,html,json,a11y.yaml}`를 생성한다.
- [x] 리팩토링 전 baseline 테스트를 실행한다.
  - [x] `PYTHONPATH=src uv run pytest`
  - [x] `PYTHONPATH=src uv run python -m compileall -q main.py src tests`

---

## Phase 1 — 계층형 State Model 추가

- [x] `src/browser/state.py`를 추가한다.
- [x] `PageState` 모델을 정의한다.
  - [x] `url: str`
  - [x] `title: str | None`
  - [x] `html_path: str | None`
  - [x] `a11y_path: str | None`
  - [x] 향후 확장용 metadata 필드 필요 여부 검토
- [x] `ViewportState` 모델을 정의한다.
  - [x] `screenshot: bytes`
  - [x] `width: int`
  - [x] `height: int`
  - [x] `scroll_x: int`
  - [x] `scroll_y: int`
- [x] `InteractionState` 모델을 정의한다.
  - [x] `focused_element: str | None`
  - [x] `available_refs: list[int]`
  - [x] `last_action: str | None`
  - [x] ARIA ref map과의 관계를 최소 필드로 시작
- [x] `BrowserState` 모델을 정의한다.
  - [x] `page: PageState`
  - [x] `viewport: ViewportState`
  - [x] `interaction: InteractionState`
- [x] 하위 호환 property를 추가한다.
  - [x] `BrowserState.url -> page.url`
  - [x] `BrowserState.screenshot -> viewport.screenshot`
- [x] migration compatibility를 위해 `EnvState`를 유지한다.
  - [x] `class EnvState(BrowserState): pass` 또는 동등한 alias 결정
- [x] `src/browser/__init__.py`에서 새 모델들을 export한다.
- [x] 모델 단위 테스트를 추가한다.
  - [x] `EnvState(...).url` 호환성
  - [x] `EnvState(...).screenshot` 호환성
  - [x] nested `page`, `viewport`, `interaction` 접근

---

## Phase 2 — Playwright current_state() 계층화

- [x] `src/browser/playwright.py`의 inline `EnvState` 정의를 `src/browser/state.py` import로 교체한다.
- [x] `PlaywrightBrowser.current_state()`가 계층형 상태를 반환하도록 수정한다.
  - [x] screenshot capture 유지
  - [x] `page.url` 채우기
  - [x] `page.title` 채우기
  - [x] viewport width/height 채우기
  - [x] scroll position 채우기
  - [x] available ARIA refs 채우기
- [x] `_write_history_snapshot()`가 artifact metadata를 반환하도록 변경한다.
  - [x] logging disabled이면 `None` 반환
  - [x] logging enabled이면 `ArtifactLogger.write_snapshot()` 결과 반환
- [x] `current_state()`에서 artifact metadata의 path 정보를 `PageState`에 반영한다.
- [x] Playwright mock 기반 테스트를 수정/추가한다.
  - [x] title 호출 mock
  - [x] viewport_size mock
  - [x] scroll position evaluate mock
  - [x] 기존 `state.url`, `state.screenshot` assertion 유지
- [x] tool handler 반환 타입이 깨지지 않는지 확인한다.

---

## Phase 3 — State Graph 데이터 생성

- [x] `src/browser/state_graph.py`를 추가한다.
- [x] `BrowserState`를 UI-friendly graph JSON으로 변환하는 함수를 만든다.
  - [x] `nodes: list[dict]`
  - [x] `links: list[dict]` 또는 `edges: list[dict]`
- [x] 최소 graph schema를 정의한다.

```json
{
  "nodes": [
    {"id": "browser", "label": "BrowserState", "type": "root"},
    {"id": "page", "label": "PageState", "type": "group"},
    {"id": "viewport", "label": "ViewportState", "type": "group"},
    {"id": "interaction", "label": "InteractionState", "type": "group"}
  ],
  "links": [
    {"source": "browser", "target": "page"},
    {"source": "browser", "target": "viewport"},
    {"source": "browser", "target": "interaction"}
  ]
}
```

- [x] leaf node value 정책을 정한다.
  - [x] 긴 URL/title은 truncate용 display label과 full value를 분리
  - [x] screenshot bytes는 graph value에 넣지 않고 size/path만 표시
  - [x] available refs는 전체 list 대신 count 중심으로 표시
- [x] graph 변환 테스트를 추가한다.
  - [x] root/group/leaf 노드 생성
  - [x] 필수 edge 생성
  - [x] sensitive/large bytes가 JSON에 포함되지 않음

---

## Phase 4 — Artifact Metadata에 State Graph 저장

- [x] `current_state()` 또는 `_write_history_snapshot()` 흐름에서 `state_graph` 저장 위치를 결정한다.
  - [x] 옵션 A: `step-XXXX.json` metadata 내부에 `state_graph` 포함
  - [x] 옵션 B: `step-XXXX.state.json` 별도 파일 생성
- [x] 1차 구현은 기존 metadata 내부 포함을 우선한다.
- [x] `ArtifactLogger.write_snapshot()`에 `metadata_extra`로 `state_graph`를 전달한다.
- [x] metadata 크기가 커지지 않도록 graph payload를 compact하게 유지한다.
- [x] logging 테스트를 보강한다.
  - [x] `step-0001.json`에 `state_graph.nodes` 존재
  - [x] `step-0001.json`에 `state_graph.links` 존재
  - [x] 기존 metadata key가 유지됨

---

## Phase 5 — UI Graph Renderer 일반화

- [x] `src/ui/panel.html`의 현재 D3 graph 책임을 분리한다.
  - [x] trajectory data builder
  - [x] D3 renderer
  - [x] tooltip formatter
- [x] 현재 graph가 `trajectoryNodes`/`trajectoryEdges`에 직접 의존하는 부분을 줄인다.
- [x] renderer update API를 일반화한다.

```js
graph.update({ nodes, links, mode })
```

- [x] 기존 navigation trajectory graph는 그대로 동작하게 유지한다.
- [x] graph node 공통 필드를 정의한다.
  - [x] `id`
  - [x] `label`
  - [x] `type`
  - [x] `value`
  - [x] `isRoot`
  - [x] `isCurrent`
- [x] graph link 공통 필드를 정의한다.
  - [x] `source`
  - [x] `target`
  - [x] `count` optional
- [x] 기존 navigation graph regression 테스트 또는 UI panel 테스트를 갱신한다.

---

## Phase 6 — BrowserState Graph UI 추가

- [x] Graph tab 내부에 mode toggle을 추가한다.
  - [x] `Trajectory`
  - [x] `Browser State`
- [x] 현재 선택된 step의 metadata에서 `state_graph`를 읽는 경로를 추가한다.
- [x] `Browser State` mode에서 state graph를 D3로 렌더링한다.
- [x] BrowserState graph용 label formatter를 추가한다.
  - [x] group node: `BrowserState`, `PageState`, `ViewportState`, `InteractionState`
  - [x] leaf node: `url`, `title`, `viewport size`, `scroll`, `available refs`
- [x] BrowserState graph용 tooltip formatter를 추가한다.
  - [x] full value 표시
  - [x] node type 표시
  - [x] source path 표시
- [x] empty state 문구를 mode별로 분리한다.
  - [x] navigation 없음
  - [x] state graph metadata 없음
- [x] 기존 D3 zoom/drag behavior를 유지한다.

---

## Phase 7 — 계층형 Layout 개선

- [x] force graph 재사용 결과를 확인한다.
  - [x] 노드가 너무 흩어지는지
  - [x] 계층 관계가 읽히는지
  - [x] step 변경 시 layout jitter가 심한지
- [x] 필요하면 BrowserState mode만 D3 tree layout으로 분리한다.
  - [x] `d3.hierarchy`
  - [x] `d3.tree()`
  - [x] 고정 depth 기반 x/y 배치
- [x] tree layout 적용 시 기존 trajectory force graph와 renderer를 분리 유지한다.
- [x] node type별 스타일을 추가한다.
  - [x] root
  - [x] group
  - [x] leaf
  - [x] changed field
- [x] leaf value가 긴 경우 UI clipping/tooltip 정책을 점검한다.

---

## Phase 8 — Step Diff 및 Action Edge 확장

- [x] 이전 step과 현재 step의 `BrowserState` diff schema를 정의한다.
- [x] diff 대상 필드를 제한한다.
  - [x] `page.url`
  - [x] `page.title`
  - [x] `viewport.scroll_x/y`
  - [x] `viewport.width/height`
  - [x] `interaction.focused_element`
  - [x] `interaction.available_refs` count
- [x] graph node에 changed marker를 추가한다.
  - [x] `changed: true`
  - [x] `previous_value`
  - [x] `current_value`
- [x] UI에서 changed node를 highlight한다.
- [x] action history와 state transition을 연결한다.
  - [x] `step N action -> step N state`
  - [x] 필요하면 별도 transition graph로 분리
- [x] diff 관련 테스트를 추가한다.

---

## Phase 9 — 정리 및 문서화

- [x] 더 이상 필요 없는 compatibility shim 제거 가능 시점을 문서화한다.
- [x] README 또는 개발 문서에 BrowserState 구조를 추가한다.
- [x] UI Graph mode 사용법을 간단히 문서화한다.
- [x] 최종 테스트를 실행한다.
  - [x] `PYTHONPATH=src uv run pytest`
  - [x] `PYTHONPATH=src uv run python -m compileall -q main.py src tests`
  - [x] 필요 시 `uv run main.py --help`
- [x] 남은 risk를 정리한다.
  - [x] mock과 실제 Playwright runtime 차이
  - [x] metadata 크기 증가
  - [x] D3 force layout readability
  - [x] UI가 external D3 CDN에 의존하는 점

---

## 권장 작업 순서 요약

- [x] Phase 1: state model 추가
- [x] Phase 2: `current_state()` 계층화
- [x] Phase 3: state graph JSON 생성
- [x] Phase 4: artifact metadata 저장
- [x] Phase 5: D3 renderer 일반화
- [x] Phase 6: UI BrowserState graph mode 추가
- [x] Phase 7: layout 개선
- [x] Phase 8: diff/action transition 확장
- [x] Phase 9: 문서화 및 cleanup
