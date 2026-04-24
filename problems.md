# 현재 레포지토리 문제점 분석

작성일: 2026-04-24  
대상 레포지토리: `tiny-browser-agent`

## 요약

현재 테스트 스위트는 통과하지만, 코드와 설정을 함께 보면 실제 기본 실행 경로에서 문제가 발생할 가능성이 높다.
가장 큰 리스크는 README가 설명하는 Gemini Computer Use 기반 동작과 실제 기본 설정(`OpenRouter` actor provider)이 서로 맞지 않는 점이다.
또한 OpenAI/OpenRouter provider의 tool-calling 어댑터, planner/subgoal 결과 전달, 파일 업로드 안전성, UI 실패 상태 표시가 주요 개선 대상이다.

확인한 검증:

```text
uv run pytest
115 passed
```

## 해결 진행 상태

- 2026-04-24: P0 “기본 설정과 README/실행 경로 불일치” 해결.
  - 기본 actor provider를 `gemini`로 되돌림.
  - 기본 actor model을 README의 Gemini Computer Use 모델(`gemini-2.5-computer-use-preview-10-2025`)과 일치시킴.
  - `vision`/`mixed` grounding이 OpenAI/OpenRouter 같은 non-computer-use provider와 결합되면 초기화 단계에서 명확히 실패하도록 검증 추가.
  - 회귀 테스트 추가 및 전체 테스트 통과 확인.
- 2026-04-24: P0 “OpenAI/OpenRouter provider의 tool-calling 어댑터 규격 문제” 해결.
  - Chat Completions role 변환에서 Google GenAI `model` role을 `assistant`로 매핑.
  - assistant tool call과 tool response message를 Chat Completions 형식으로 직렬화.
  - tool-call id를 provider 응답에서 보존하고 tool executor의 `FunctionResponse`까지 전파.
  - function parameter schema를 OpenAI 호환 JSON Schema(`object`, `array`, `string` 등 소문자 type)로 생성/정규화.
  - OpenRouter actor 호출에 Google 전용 `thinking_config` payload를 보내지 않도록 정리.
  - 회귀 테스트 추가 및 전체 테스트 통과 확인.
- 2026-04-24: P1 “Planner/subgoal 모드 최종 결과 전달 문제” 해결.
  - subgoal 실행 결과를 전체 planner task 최종 summary로 집계.
  - subgoal mode 완료 시 `review_metadata_extracted`와 `step_complete` final event를 emit해 CLI/UI에서 최종 결과를 볼 수 있게 함.
  - CLI와 UI session 모두 PlannerAgent의 `replan` callback을 BrowserAgent에 연결.
  - 회귀 테스트 추가 및 전체 테스트 통과 확인.
- 2026-04-24: P1 “upload_file 도구의 파일 유출 가능성” 완화.
  - `PlaywrightBrowser`에 upload allowlist root 검증 추가.
  - 기본 허용 root를 현재 작업 디렉터리와 시스템 temp 디렉터리로 제한.
  - symlink 우회를 줄이기 위해 업로드 대상 경로를 `resolve(strict=True)`로 정규화한 뒤 allowlist를 검사.
  - 허용 범위 밖 파일은 file chooser를 열기 전에 `PermissionError`로 차단.
  - 회귀 테스트 추가 및 전체 테스트 통과 확인.
- 2026-04-24: P1 “UI session 실패 상태가 task_complete로 표시됨” 해결.
  - agent 실행 예외 시 `task_complete` 대신 `task_failed`를 emit하도록 변경.
  - 실패 시 browser reset 후 즉시 return해 성공 완료 이벤트가 섞이지 않게 함.
  - UI panel에 `task_failed` 처리 추가.
  - WebSocket late-join replay 대상 session event에 `task_failed` 추가.
  - 회귀 테스트 추가 및 전체 테스트 통과 확인.
- 2026-04-24: P2 “테스트 커버리지의 통합 경로 공백” 보강.
  - 기본 actor config가 Gemini Computer Use 모델을 가리키는지 검증하는 테스트 추가.
  - 기본 config provider로 BrowserAgent가 `vision` grounding 초기화를 통과하는지 검증하는 테스트 추가.
  - OpenAI/OpenRouter actor용 `generate_content()`의 tool-call request/response 왕복 테스트 추가.
  - tool-call id가 provider 응답에서 executor `FunctionResponse`까지 보존되는지 검증하는 테스트 추가.

## 우선순위별 문제 목록

| 우선순위 | 문제 | 신뢰도 | 영향 |
| --- | --- | --- | --- |
| P0 (해결됨) | 기본 설정과 README/실행 경로가 불일치함 | 높음 | 기본 실행 시 브라우저 조작이 제대로 동작하지 않을 수 있음 |
| P0 (해결됨) | OpenAI/OpenRouter provider의 tool-calling 어댑터가 Chat Completions 규격과 맞지 않을 가능성이 큼 | 높음 | function calling 왕복이 실패하거나 모델이 도구를 제대로 호출하지 못할 수 있음 |
| P1 (해결됨) | Planner/subgoal 모드 결과가 최종 사용자 응답으로 잘 합쳐지지 않음 | 높음 | 작업은 진행되지만 사용자가 최종 결과를 명확히 받지 못할 수 있음 |
| P1 (완화됨) | `upload_file` 도구가 모델이 지정한 임의의 절대경로 파일을 업로드할 수 있음 | 중상 | 민감 파일 유출 가능성 |
| P1 (해결됨) | UI session은 agent 예외 발생 후에도 `task_complete`를 emit함 | 높음 | 실패한 작업이 UI에서 성공/완료처럼 보일 수 있음 |
| P2 (보강됨) | 현재 테스트는 기본 config + provider + tool-calling 통합 경로를 충분히 검증하지 않음 | 중간 | 실제 실행 장애가 unit test에서 누락될 수 있음 |

---

## 1. 기본 설정과 README/실행 경로 불일치

### 증상

README는 프로젝트를 Gemini Computer Use 기반 브라우저 agent로 설명하지만, 실제 기본 actor provider는 `openrouter`로 설정되어 있다.
CLI의 기본 grounding은 `vision`이고, `vision` 모드는 Google Gemini Computer Use tool을 사용하는 구조다.
하지만 OpenRouter/OpenAI provider는 `computer_use` tool을 HTTP 요청에 반영하지 않는다.

### 근거

- `README.md`
  - 프로젝트 설명: Gemini Computer Use 기반.
  - 요구사항: Gemini API key.
  - quick start: `GEMINI_API_KEY` 설정 후 실행.
- `config.yaml`
  - `models.actor.provider: openrouter`
  - `models.actor.model: nvidia/nemotron-3-super-120b-a12b:free`
- `main.py`
  - `--grounding` 기본값은 `vision`.
- `src/tool_executor.py`
  - `vision` 모드는 `types.Tool(computer_use=...)`와 custom function declarations를 구성.
- `src/llm/provider/openai.py`, `src/llm/provider/openrouter.py`
  - provider들은 `tool.function_declarations`만 Chat Completions `tools`로 변환하고 `tool.computer_use`는 변환하지 않음.

### 영향

기본 설정으로 실행하면 README가 기대시키는 Gemini Computer Use 브라우저 조작 경로가 아니라 OpenRouter 기반 text/tool-call 경로로 들어간다.
이 경우 `click_at`, `navigate`, `scroll_document` 같은 핵심 browser action이 모델에 제대로 노출되지 않을 수 있다.

---

## 2. OpenAI/OpenRouter tool-calling 어댑터 규격 문제

### 증상

OpenAI/OpenRouter provider가 Google GenAI `Content`/`Part` 구조를 Chat Completions 메시지로 단순 문자열 변환한다.
이 과정에서 role, tool response, schema type 등이 Chat Completions 규격과 어긋날 가능성이 높다.

### 근거

- `src/llm/provider/openai.py`
  - `_contents_to_messages()`가 `content.role`을 그대로 message role로 사용.
  - Google GenAI의 model role은 Chat Completions에서 일반적으로 assistant role로 변환되어야 하지만 현재 그대로 전달됨.
  - `function_response`는 tool message가 아니라 `"[Function response: ...]"` 텍스트로 변환됨.
  - tool schema type이 Google enum style인 `"OBJECT"`, `"STRING"` 등으로 직렬화됨.
- `src/llm/provider/openrouter.py`
  - OpenAI provider와 거의 같은 변환 구조.
  - 추가로 `thinking_config`를 OpenRouter body에 넣지만, 모델/라우터별 호환성이 보장되는지 코드상 확인되지 않음.

### 영향

모델이 tool call을 반환하지 못하거나, 반환해도 다음 turn에서 tool 결과를 올바르게 인식하지 못할 수 있다.
특히 OpenAI/OpenRouter provider를 actor로 사용할 때 browser automation loop가 불안정해질 가능성이 크다.

---

## 3. Planner/subgoal 모드 최종 결과 전달 문제

### 증상

Planner가 subgoal을 만들고 BrowserAgent가 subgoal별 실행은 하지만, 전체 작업 결과를 사용자에게 자연스럽게 종합해서 전달하는 단계가 부족하다.
레포지토리의 `TODO.md`에도 같은 문제가 직접 기록되어 있다.

### 근거

- `TODO.md`
  - “subgoal 로 나눠서 진행자체는 잘 되는데 결과물이 사용자에게 제대로 전달이 안되는 것 같음.”
- `src/agents/actor_agent.py`
  - `_run_subgoal_loop()`는 각 subgoal에 대해 `SUBGOAL_DONE:` 또는 `SUBGOAL_FAILED:` marker만 판정.
  - `agent_loop()`는 subgoal queue를 순회하지만 전체 subgoal 완료 후 최종 요약/종합 응답을 생성하지 않음.
- `main.py`, `src/session.py`
  - PlannerAgent는 생성하지만 `replan_callback`은 BrowserAgent에 전달하지 않음.

### 영향

작업 단계는 수행되더라도 CLI/UI 사용자에게 “최종적으로 무엇을 찾았는지/완료했는지”가 불명확하게 전달될 수 있다.
또한 실패한 subgoal 이후 재계획 기능도 현재 기본 CLI/UI 경로에서는 사실상 연결되어 있지 않다.

---

## 4. `upload_file` 도구의 파일 유출 가능성

### 증상

`upload_file` 도구는 모델이 지정한 절대경로가 실제 존재하는지만 확인하고, 해당 파일을 페이지의 file input에 업로드한다.
업로드 가능한 경로에 대한 allowlist, workspace 제한, 사용자 확인 절차가 없다.

### 근거

- `src/browser/actions.py`
  - `upload_file(x, y, path)`는 path를 받아 denormalize 후 `browser_computer.upload_file(...)`로 전달.
- `src/browser/playwright.py`
  - `upload_file()`은 path가 absolute인지, 존재하는지만 검사.
  - 이후 `file_chooser.set_files(str(resolved_path))` 실행.
- `src/agents/actor_agent.py`
  - safety confirmation은 모델이 `safety_decision` argument를 넣었을 때만 작동.

### 영향

악성/오작동 모델 출력 또는 prompt injection에 의해 로컬 민감 파일이 웹페이지에 업로드될 가능성이 있다.
브라우저 agent 특성상 파일 업로드는 명시적 사용자 승인 또는 안전한 경로 제한이 필요하다.

---

## 5. UI session 실패 상태가 `task_complete`로 표시됨

### 증상

UI session에서 agent 실행 중 예외가 발생해도 `step_error`를 emit한 뒤 항상 `task_complete`를 emit한다.

### 근거

- `src/session.py`
  - `run_task()`에서 `agent.agent_loop()` 예외를 잡아 `step_error`를 emit.
  - 이후 함수 마지막에서 무조건 `emit({"type": "task_complete", ...})` 실행.
- `src/ui/panel.html`
  - `task_complete` 이벤트를 받으면 상태를 ready로 되돌리고 “task complete” 블록을 추가.

### 영향

실패한 작업이 UI상 완료된 것처럼 보일 수 있다.
사용자가 실패를 성공으로 오해하거나, 실제 오류 원인을 놓칠 수 있다.

---

## 6. 테스트 커버리지의 통합 경로 공백

### 증상

현재 unit test는 104개 모두 통과하지만, 주요 위험 경로는 대부분 mock 기반 테스트로는 검증되지 않는다.

### 근거

- `tests/test_agent.py`, `tests/test_tool_calling.py`
  - BrowserAgent와 tool executor 동작을 주로 mock으로 검증.
- `tests/test_action_step_summarizer.py`
  - OpenAI/OpenRouter provider의 `generate_text()`는 검증하지만 actor용 `generate_content()`의 실제 tool-call request/response 왕복은 충분히 검증하지 않음.
- `config.yaml`
  - 기본 actor provider가 OpenRouter인데, 이 기본 설정 조합으로 browser action loop가 성립하는지 검증하는 테스트가 보이지 않음.

### 영향

단위 테스트 통과와 실제 실행 가능성 사이에 간극이 있다.
특히 provider 어댑터와 grounding mode 조합 문제는 integration test 없이는 재발하기 쉽다.

---

## 권장 확인 순서

수정 작업을 시작한다면 다음 순서가 가장 위험을 줄인다.

1. 기본 실행 정책 결정
   - Gemini Computer Use를 기본으로 유지할지
   - OpenRouter/OpenAI actor를 기본으로 삼되 text/mixed grounding만 지원할지
2. provider별 허용 grounding 검증 추가
   - incompatible config는 초기화 단계에서 명확히 실패시키기
3. OpenAI/OpenRouter Chat Completions adapter 정비
   - role mapping
   - tool schema JSON Schema 변환
   - tool call / tool response message round-trip
4. Planner/subgoal 최종 요약 이벤트 및 CLI 출력 추가
5. `upload_file`에 사용자 확인 또는 안전 경로 제한 추가
6. UI 실패 이벤트를 `task_failed`와 `task_complete`로 분리
7. 현재 기본 `config.yaml` 조합을 대상으로 한 최소 integration/regression test 추가

## 현재 확인된 상태

- P0 기본 설정/grounding/provider 불일치 문제는 수정됨.
- P0 OpenAI/OpenRouter provider tool-calling adapter 문제는 수정됨.
- P1 Planner/subgoal 최종 결과 전달 문제는 수정됨.
- P1 `upload_file` 파일 유출 가능성은 allowlist root 제한으로 완화됨.
- P1 UI session 실패 상태 표시 문제는 수정됨.
- P2 테스트 커버리지의 통합 경로 공백은 기본 config/provider/tool-call 회귀 테스트로 보강됨.
- 기존 테스트와 신규 회귀 테스트 기준으로는 `115 passed`.
