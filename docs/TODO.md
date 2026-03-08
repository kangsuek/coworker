# 버그 수정 TODO 목록

기반 보고서: `docs/research.md`
작성일: 2026-03-08

---

## Critical

- [ ] **BUG-C01** `_cancelled_runs` 조기 정리 수정
  - `session_service.py:update_run_status` — `"cancelled"` 케이스를 `_cancelled_runs.discard` 대상에서 제거
  - `reader.py:process_message` — 함수 끝 `finally` 블록에서 `_cancelled_runs.discard(run_id)` 직접 호출
  - 영향: 취소 후에도 CLI가 실행되어 응답이 저장되는 현상 해결

- [ ] **BUG-C02** 세션 삭제 시 취소 시그널 정리 순서 수정
  - `sessions.py:delete_session` — `update_run_status("cancelled")` 호출 제거 또는 순서 조정
  - 세션/런 DB 삭제 전에 백그라운드 태스크가 graceful하게 종료될 수 있도록 처리

---

## High

- [ ] **BUG-H01** LLM 분류 태스크 누락 방지
  - `classification.py:_classify_with_llm` — 반환된 에이전트 수가 원본보다 적을 때 경고 로그 출력 + 원본 유지 폴백

- [ ] **BUG-H02** 팀 모드 통합 단계 취소 처리
  - `reader.py:_team_execute` — `asyncio.gather` 완료 후 `_integrate_results` 호출 전 취소 여부 재확인
  - `_cancelled_runs` 또는 DB status 체크 후 이미 취소된 경우 조기 반환

---

## Medium

- [ ] **BUG-M01** `LineBufferFlusher` 이벤트 루프 블로킹 수정
  - `cli_service.py:LineBufferFlusher` — `threading.Lock` 대신 thread-safe한 `collections.deque` 또는 `queue.SimpleQueue` 사용

- [ ] **BUG-M02** `App.tsx` 렌더 내 `setState` 제거
  - `App.tsx:71-75` — `prevSessionId` 비교 블록을 `useEffect([session.currentSession?.id])` 로 이전

- [ ] **BUG-M03** `handleSend` 이중 제출 방지
  - `UserChannel/index.tsx:handleSend` — `submitting` state 대신 `useRef` 플래그를 사용하여 즉시 잠금

- [ ] **BUG-M04** SSE 무한 재연결 제한
  - `useRunSSE.ts` — 최대 재시도 횟수(`MAX_RECONNECT_ATTEMPTS`) 추가, 초과 시 `/runs/{run_id}` 폴링으로 전환

---

## Low

- [ ] **BUG-L01** `useAgentPolling.ts` 데드 코드 삭제
  - `frontend/src/hooks/useAgentPolling.ts` 파일 삭제

- [ ] **BUG-L02** 세션 제목 자동 설정 시 메모리 트리거 제외
  - `session_service.py:create_user_message` — `settings.memory_trigger` 를 트리거 제외 목록에 추가

- [ ] **BUG-L03** 팀 모드 `run_id` 연결 로직 개선
  - `sessions.py:get_session` — 역방향 탐색 대신 `run_map`의 `user_message_id` 직접 매핑 활용

---

## 보안

- [ ] **SEC-04** Gemini CLI 프롬프트 인젝션 방지
  - `gemini_cli.py` — `gemini --system-prompt` 플래그 지원 여부 확인 후 분리 전달
  - 미지원 시: 구분자 강화 (`<system>...</system><user>...</user>` 형식 등)

- [ ] **SEC-02** 메시지 입력 길이 제한
  - `schemas.py:ChatRequest.message` — `Field(max_length=50000)` 추가
  - `session_service.py:create_user_message` — content 길이 검증

- [ ] **SEC-03** API Rate Limiting 적용
  - `main.py` — `slowapi` 또는 `fastapi-limiter` 도입
  - `/api/chat` 엔드포인트 IP당 분당 요청 수 제한

- [ ] **SEC-01** CORS 허용 범위 축소
  - `main.py` — `allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]`, `allow_headers=["Content-Type"]` 로 명시

- [ ] **SEC-05** 커스텀 역할 입력 검증
  - `reader.py` — `role_name` 최대 길이 제한, `prompt` 최대 길이 제한 추가

---

## 설계 개선

- [ ] **DES-01** `execute_with_lock` 함수명 변경
  - `cli_service.py` — `execute_with_lock` → `execute_if_not_cancelled` 로 rename (호출부 모두 수정)

- [ ] **DES-02** 취소 상태 단일화
  - BUG-C01 수정과 연계: `_cancelled_runs`를 유일한 취소 시그널로 사용하고, DB status는 최종 확인용으로만 사용하는 구조로 문서화
