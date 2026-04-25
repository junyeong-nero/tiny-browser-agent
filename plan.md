# Code Simplification Refactoring Plan

## 목표

- 기존 동작을 유지하면서 중복, 얇은 위임 계층, 반복 조건문을 줄인다.
- 새 의존성 없이 작은 단위의 변경으로 진행한다.
- 각 단계는 테스트로 보호한 뒤 리팩토링하고, 단계별로 검증한다.

## 기본 원칙

- [ ] 리팩토링 전 현재 전체 테스트 상태를 확인한다: `uv run pytest`
- [ ] 동작 변경이 아닌 구조 단순화를 우선한다.
- [ ] 새 추상화는 중복 제거 효과가 명확한 경우에만 추가한다.
- [ ] private API를 직접 호출하는 테스트는 가능하면 실제 책임 객체 단위 테스트로 옮긴다.
- [ ] 각 단계 후 관련 테스트를 먼저 실행하고, 마지막에 전체 테스트를 실행한다.
- [ ] 변경 범위가 커지는 경우 단계를 더 잘게 나눈다.

## 1. Provider 중복 제거: OpenAI / OpenRouter

- [ ] `src/llm/provider/openai.py`와 `src/llm/provider/openrouter.py`의 공통 흐름을 비교한다.
- [ ] 기존 테스트에서 OpenAI/OpenRouter provider 요청 payload와 응답 변환을 보호하는 테스트가 충분한지 확인한다.
- [ ] 부족하면 `tests/test_llm_providers.py` 또는 기존 provider 테스트에 회귀 테스트를 추가한다.
- [ ] 공통 HTTP Chat Completions provider base/helper를 만든다.
  - [ ] request body 구성 공통화
  - [ ] `generate_text()` 공통화
  - [ ] `generate_content()` 공통화
  - [ ] `_extract_text()` 공통화
  - [ ] SSL context 생성 공통화
- [ ] OpenAI 전용 차이는 최소 필드만 남긴다.
  - [ ] env var: `OPENAI_API_KEY`, `OPENAI_BASE_URL`
  - [ ] error prefix: `OpenAI`
  - [ ] 기본 base URL
- [ ] OpenRouter 전용 차이는 최소 필드만 남긴다.
  - [ ] env var: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`
  - [ ] optional headers: `HTTP-Referer`, `X-Title`
  - [ ] error prefix: `OpenRouter`
  - [ ] 기본 base URL
- [ ] 관련 테스트를 실행한다.
  - [ ] `uv run pytest tests/test_llm_client.py`
  - [ ] provider 테스트 파일이 있으면 함께 실행한다.

## 2. ActionReviewService 조건문 테이블화

- [ ] `ActionReviewService.build_action_summary()`의 action별 문자열을 데이터 테이블로 정리한다.
- [ ] `ActionReviewService.build_fallback_reason()`의 action별 fallback reason을 데이터 테이블로 정리한다.
- [ ] `ActionReviewService.build_phase_metadata()`의 action group 분류를 상수 테이블로 정리한다.
- [ ] 동적 포맷이 필요한 action은 작은 formatter 함수로만 남긴다.
  - [ ] `click_at`
  - [ ] `hover_at`
  - [ ] `type_text_at`
  - [ ] `scroll_at`
  - [ ] `navigate`
  - [ ] `key_combination`
  - [ ] `drag_and_drop`
- [ ] ambiguity detection 동작은 변경하지 않는다.
- [ ] 관련 테스트를 실행한다.
  - [ ] `uv run pytest tests/test_agent.py tests/test_action_step_summarizer.py tests/test_ambiguity_detector.py`

## 3. BrowserAgent의 얇은 위임 메서드 축소

- [ ] `BrowserAgent`의 `_build_*` wrapper 중 단순 위임만 하는 메서드를 목록화한다.
- [ ] 테스트가 직접 호출하는 private wrapper를 확인한다.
  - [ ] `_build_persisted_action_metadata()`
  - [ ] `_build_review_metadata_for_action()`
  - [ ] 기타 `_build_*` wrapper
- [ ] private wrapper 대상 테스트를 가능하면 `ActionReviewService` 단위 테스트로 이동한다.
- [ ] 내부 호출부가 service를 직접 호출하도록 단순화한다.
- [ ] 외부에서 의미 있게 쓰이는 wrapper는 유지하고, 사용되지 않는 wrapper만 제거한다.
- [ ] 관련 테스트를 실행한다.
  - [ ] `uv run pytest tests/test_agent.py tests/test_action_step_summarizer.py`

## 4. Tool handler 반복 축소

- [ ] `src/tools/*`의 좌표 denormalize 반복 패턴을 확인한다.
- [ ] 공통 helper 후보를 정한다.
  - [ ] normalized point 변환 helper
  - [ ] normalized magnitude 변환 helper
  - [ ] ref locator resolve helper
- [ ] 파일 통합보다 작은 helper 도입을 우선 검토한다.
- [ ] 지나친 추상화가 되면 현 구조를 유지한다.
- [ ] `BrowserToolExecutor._handlers` 등록 방식이 더 단순해질 수 있는지 확인한다.
- [ ] 관련 테스트를 실행한다.
  - [ ] `uv run pytest tests/test_tool_calling.py tests/test_semantic_tools.py`

## 5. PlaywrightBrowser action 반복 정리

- [ ] action 후 `wait_for_load_state()` / `current_state()` 반복 지점을 정리한다.
- [ ] helper 도입 전, Playwright timeout/error behavior가 바뀌지 않는지 확인한다.
- [ ] 안전한 범위에서만 helper화한다.
  - [ ] simple navigation actions
  - [ ] simple mouse actions
  - [ ] keyboard actions
- [ ] 복합 action은 가독성이 나빠지면 유지한다.
  - [ ] `type_text_at()`
  - [ ] `drag_and_drop()`
  - [ ] `upload_file()`
- [ ] 관련 테스트를 실행한다.
  - [ ] `uv run pytest tests/test_playwright_logging.py tests/test_playwright_upload.py tests/test_semantic_tools.py`

## 6. 캐시/산출물 정리

- [ ] `src/**/__pycache__`와 `tests/**/__pycache__`가 git 추적 대상인지 확인한다.
- [ ] 추적 대상이 아니면 삭제 여부를 별도 작업으로 판단한다.
- [ ] `.gitignore`가 Python 캐시를 포함하는지 확인한다.
- [ ] 필요하면 `.gitignore`에 누락된 캐시 패턴만 추가한다.

## 최종 검증

- [ ] 전체 테스트 실행: `uv run pytest`
- [ ] 정적 컴파일 확인: `uv run python -m compileall -q main.py src tests`
- [ ] CLI 도움말 확인: `uv run main.py --help`
- [ ] 변경 파일을 검토해 동작 변경이 섞이지 않았는지 확인한다.
- [ ] 남은 리스크를 기록한다.

## 권장 작업 순서

- [ ] 1단계: Provider 중복 제거
- [ ] 2단계: ActionReviewService 조건문 테이블화
- [ ] 3단계: BrowserAgent wrapper 축소
- [ ] 4단계: Tool handler helper화
- [ ] 5단계: PlaywrightBrowser 반복 정리
- [ ] 6단계: 캐시/산출물 정리

## 보류 기준

- [ ] 테스트가 private implementation detail에 과도하게 묶여 있어 리팩토링보다 테스트 이동이 먼저 필요한 경우
- [ ] 추상화 도입 후 코드가 더 읽기 어려워지는 경우
- [ ] provider별 API 차이로 공통 base가 조건문 투성이가 되는 경우
- [ ] Playwright timing/wait behavior가 조금이라도 바뀔 가능성이 있는 경우
