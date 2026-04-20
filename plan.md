# Refactoring Plan: `src/tool_calling.py` 분리

## 목표

`src/tool_calling.py` 의 책임을 아래 두 영역으로 분리한다:
- `src/tools/` — 각 브라우저 툴의 핸들러 로직
- `src/tool_executor.py` — 실행 오케스트레이션, 직렬화, 컨텍스트 관리

---

## 현재 구조

```
src/tool_calling.py
├── PREDEFINED_COMPUTER_USE_FUNCTIONS  (상수)
├── EnvStateLike, is_env_state_result  (프로토콜/타입 가드)
├── ToolResult, CustomFunction         (타입 앨리어스)
├── ExecutedCall, ToolBatchResult      (데이터클래스)
├── BrowserToolExecutor                (실행 클래스 + 13개 핸들러)
└── prune_old_screenshot_parts         (컨텍스트 유틸리티)
```

---

## 목표 구조

```
src/
├── tools/
│   ├── __init__.py              # 공개 API 재-export
│   ├── types.py                 # EnvStateLike, ToolResult, CustomFunction,
│   │                            # ExecutedCall, ToolBatchResult, is_env_state_result
│   ├── constants.py             # PREDEFINED_COMPUTER_USE_FUNCTIONS
│   ├── open_web_browser.py      # handle_open_web_browser
│   ├── click_at.py              # handle_click_at
│   ├── hover_at.py              # handle_hover_at
│   ├── type_text_at.py          # handle_type_text_at
│   ├── scroll_document.py       # handle_scroll_document
│   ├── scroll_at.py             # handle_scroll_at
│   ├── wait_5_seconds.py        # handle_wait_5_seconds
│   ├── go_back.py               # handle_go_back
│   ├── go_forward.py            # handle_go_forward
│   ├── search.py                # handle_search
│   ├── navigate.py              # handle_navigate
│   ├── key_combination.py       # handle_key_combination
│   └── drag_and_drop.py         # handle_drag_and_drop
└── tool_executor.py             # BrowserToolExecutor, prune_old_screenshot_parts
```

---

## 각 툴 파일 인터페이스

각 `src/tools/<tool_name>.py` 는 동일한 시그니처를 따른다:

```python
# src/tools/click_at.py
from computers import Computer, EnvState
from tools.types import denormalize_x, denormalize_y  # 공유 좌표 변환 유틸

def handle_click_at(computer: Computer, args: dict) -> EnvState:
    return computer.click_at(
        x=denormalize_x(args["x"], computer),
        y=denormalize_y(args["y"], computer),
    )
```

> **Note**: `denormalize_x / denormalize_y` 는 현재 `BrowserToolExecutor` 메서드인데,
> `Computer` 인스턴스를 받는 순수 함수로 `tools/types.py` 에 이동시킨다.

---

## `src/tool_executor.py` 책임

현재 `BrowserToolExecutor` 에서 아래 책임만 남긴다:

| 메서드 | 설명 |
|--------|------|
| `build_tools()` | Gemini Tool 선언 빌드 |
| `execute_call()` | 단일 `FunctionCall` 실행 + `ExecutedCall` 반환 |
| `serialize_function_response()` | `ExecutedCall` → `FunctionResponse` 직렬화 |
| `execute()` | 핸들러 디스패치 (handler map 조회) |
| `_latest_artifact_metadata()` | 아티팩트 메타데이터 조회 |

핸들러 맵은 각 파일에서 함수를 import 해서 구성:

```python
from tools.click_at import handle_click_at
from tools.navigate import handle_navigate
# ...

self._handlers = {
    "click_at": lambda args: handle_click_at(self._browser_computer, args),
    "navigate": lambda args: handle_navigate(self._browser_computer, args),
    # ...
}
```

---

## 단계별 작업

### Phase 1 — 타입/상수 분리

- [ ] `src/tools/types.py` 생성: `EnvStateLike`, `is_env_state_result`, `ToolResult`, `CustomFunction`, `ExecutedCall`, `ToolBatchResult`, `denormalize_x`, `denormalize_y`
- [ ] `src/tools/constants.py` 생성: `PREDEFINED_COMPUTER_USE_FUNCTIONS`
- [ ] `src/tools/__init__.py` 생성 (빈 파일)

### Phase 2 — 개별 툴 파일 생성

- [ ] 13개 툴 핸들러를 각각 `src/tools/<tool_name>.py` 로 분리
- [ ] 각 파일은 `handle_<tool_name>(computer: Computer, args: dict) -> EnvState` 형태

### Phase 3 — `tool_executor.py` 작성

- [ ] `src/tool_executor.py` 생성
- [ ] `BrowserToolExecutor` 이동 (핸들러 메서드 제거, import 방식으로 교체)
- [ ] `prune_old_screenshot_parts` 이동
- [ ] `src/tools/__init__.py` 에서 공개 API 재-export

### Phase 4 — 기존 파일 정리 및 import 수정

- [ ] `src/agent.py` import 경로 수정
  ```python
  # Before
  from tool_calling import BrowserToolExecutor, prune_old_screenshot_parts
  # After
  from tool_executor import BrowserToolExecutor, prune_old_screenshot_parts
  ```
- [ ] `src/tool_calling.py` 삭제

### Phase 5 — 검증

- [ ] 기존 테스트 통과 확인
- [ ] 타입 체크 (`pyright` / `mypy`) 통과 확인
- [ ] 에이전트 실행 smoke test

---

## 주의사항

- `BrowserToolExecutor` 의 public API (`build_tools`, `execute_call`, `serialize_function_response`) 는 변경하지 않는다 — `agent.py` 의 호출부를 건드리지 않아야 한다.
- 좌표 변환 `denormalize_x/y` 를 순수 함수로 만들 때 `screen_size()` 호출이 `Computer` 인스턴스에 의존하므로 함수 시그니처에 `computer` 파라미터를 명시적으로 받는다.
