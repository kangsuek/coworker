# Coworker Phase 1 — 개발 진행 체크리스트

> **기준 문서**: `DEVELOPMENT_PLAN.md` (PRD v1.2.0)
> **최종 갱신**: 2026-02-28
> **개발 방법론**: **TDD (Test-Driven Development)**
> **범례**: ✅ 완료 · 🔧 진행 중 · ⬜ 미착수 · ❌ 차단/이슈 · 🚫 게이트 차단

---

## TDD 개발 규칙

> **모든 기능 개발은 반드시 TDD 사이클(Red → Green → Refactor)을 따른다.**

### 태스크 내 TDD 사이클

```
1. 🔴 RED    — 실패하는 테스트를 먼저 작성한다
2. 🟢 GREEN  — 테스트를 통과하는 최소한의 코드를 작성한다
3. 🔵 REFACTOR — 테스트가 통과하는 상태를 유지하며 코드를 개선한다
```

### Sprint 간 게이트 규칙

- **다음 Sprint 진입 전 현재 Sprint의 모든 테스트가 100% 통과해야 한다**
- 게이트 검증: `just test` (= `cd backend && uv run pytest -v`) 전체 실행
- 1개라도 실패하면 다음 Sprint 진행 금지 (🚫 게이트 차단)
- 프론트엔드: `cd frontend && npm run lint && npx tsc --noEmit` 타입 체크 통과 필수

### Sprint 내 태스크 순서

각 태스크는 아래 순서를 엄격히 따른다:

1. **테스트 파일 생성** — 테스트 함수 작성 (이 시점에서 테스트는 실패해야 함)
2. **구현 코드 작성** — 테스트를 통과시키는 코드 작성
3. **테스트 실행 및 통과 확인** — `pytest -v` 해당 테스트 파일 100% 통과
4. **리팩토링** — 테스트 통과 상태를 유지하며 코드 개선
5. **전체 테스트 재실행** — 기존 테스트 회귀 없음 확인

### Claude Code Plan 라벨

- `[Plan: High]`: 구현 전 Plan 모드 권장 (아키텍처/상태 전이/API 영향이 큰 작업)
- `[Plan: Medium]`: 짧은 설계 정리 후 진행 권장
- `[Plan: Skip]`: Plan 모드 생략 가능, 바로 TDD RED 단계 진입 가능

### 작업 시작 전 체크리스트 (`[Plan: High]` 전용)

아래 항목은 구현 시작 전에 Plan 모드로 작업 분해/리스크를 먼저 정리한다.

- [x] `2-1` CLI 서비스 구현 (Popen + 라인 스트리밍)
- [x] `2-2` Global Execution Lock 구현
- [x] `2-3` JSON 파싱 폴백 체인 구현
- [x] `3-1` Reader Agent 구현 (분류 + Solo 응답)
- [x] `3-2~3-3` REST 엔드포인트 구현 (chat, runs)
- [x] `3-5` 백그라운드 실행 관리 (BackgroundTasks)
- [ ] `5-1` Sub-Agent 기반 클래스 구현
- [ ] `5-3` Context Assembler 구현
- [ ] `5-4` Team 오케스트레이션 루프 구현
- [ ] `5-7` 취소 기능 구현

### 작업 시작 전 체크리스트 (`[Plan: Medium]` 전용)

아래 항목은 구현 전에 5~10분 수준의 미니 Plan 정리(입력/출력, 상태 변화, 테스트 범위) 후 시작한다.

- [x] `2-4` 세션 CRUD 서비스
- [x] `3-4` 세션 엔드포인트 구현 (목록·상세·생성)
- [ ] `4-2` `useRunPolling` 훅 구현
- [ ] `4-3` `useSession` 훅 구현
- [ ] `5-2` 5개 프리셋 시스템 프롬프트 구현
- [ ] `5-5` Agent Channel DB 기록 구현
- [ ] `5-6` `GET /api/runs/{run_id}/agent-messages` 구현
- [ ] `6-1` `useAgentPolling` 훅 구현
- [ ] `6-4` Team 상태 표시 (User Channel)
- [ ] `6-5` 취소 버튼 구현

---

## 전체 진행 요약

| Sprint | 이름 | 기간 | 상태 | 태스크 진행 | 테스트 게이트 |
|:------:|------|:----:|:----:|:----------:|:----------:|
| 1 | 프로젝트 기반 구축 | 3일 | ✅ 완료 | 8/8 | ✅ 통과 |
| 2 | CLI 서비스 및 핵심 인프라 | 4일 | ✅ 완료 | 5/5 | ✅ 통과 |
| 3 | Solo 모드 End-to-End | 4일 | ✅ 완료 | 6/6 | ✅ 통과 |
| 4 | 프론트엔드 기초 및 Solo UI | 5일 | ✅ 완료 | 9/9 | ✅ 통과 |
| 5 | Team 모드 백엔드 | 5일 | ⬜ 미착수 | 0/8 | ⬜ 미검증 |
| 6 | Team UI 및 마무리 | 5일 | ⬜ 미착수 | 0/9 | ⬜ 미검증 |

### 마일스톤

| 마일스톤 | 시점 | 상태 |
|---------|------|:----:|
| **M1**: Solo E2E (메시지 → Solo 응답 → UI 표시 → 세션 저장) | Sprint 3~4 완료 | ⬜ |
| **M2**: Phase 1 완료 (Team 포함 전체 동작, PRD Section 12 성공 기준) | Sprint 6 완료 | ⬜ |

---

## Sprint 1: 프로젝트 기반 구축 ✅

> **목표**: 개발 환경 셋업, 프로젝트 스캐폴딩, DB 스키마 생성
> **PRD 참조**: Section 9

### 태스크

- [x] **1-1. 프로젝트 루트 구조 생성**
  - [x] `justfile` 작성 (dev, backend, frontend, setup, migrate, test, lint)
  - [x] `.env.example` 작성
  - [x] `.gitignore` 작성
  - [x] `just setup` 명령 동작 확인

- [x] **1-2. 백엔드 프로젝트 초기화**
  - [x] `backend/pyproject.toml` 생성 (uv, ruff, pytest 설정)
  - [x] `backend/.env.example` 생성
  - [x] `cd backend && uv sync` 성공 확인

- [x] **1-3. FastAPI 앱 스켈레톤**
  - [x] `backend/app/main.py` — FastAPI 인스턴스 생성
  - [x] CORS 미들웨어 설정 (`settings.cors_origin_list`)
  - [x] `lifespan` 이벤트에서 WAL pragma 실행
  - [x] chat, sessions 라우터 등록 (`/api` 프리픽스)
  - [x] `/api/health` 헬스체크 엔드포인트
  - [x] `just backend` → Swagger UI (`/docs`) 접속 확인

- [x] **1-4. SQLAlchemy 모델 정의**
  - [x] `backend/app/models/db.py` 생성
  - [x] `Session` 테이블 (id, title, created_at, updated_at)
  - [x] `UserMessage` 테이블 (id, session_id FK, role, content, mode, created_at)
  - [x] `AgentMessage` 테이블 (id, session_id FK, run_id, sender, role_preset, content, status, created_at)
  - [x] `Run` 테이블 (id, session_id FK, user_message_id FK, mode, status, agent_count, started_at, finished_at)
  - [x] 모든 PK는 UUID (`uuid4`)
  - [x] `aiosqlite` async engine + `async_sessionmaker`
  - [x] `run_pragmas()` — WAL 모드 + busy_timeout=5000
  - [x] `_set_sqlite_pragmas()` — sync engine connect 이벤트 리스너
  - [x] `get_db()` 의존성 함수

- [x] **1-5. Alembic 초기화 + 마이그레이션**
  - [x] `backend/alembic.ini` 생성
  - [x] `backend/migrations/env.py` — async 지원, 프로젝트 settings DB URL 사용
  - [x] 초기 마이그레이션 생성 (`bdf9c29f78a5_initial_tables.py`)
  - [x] `just migrate` → SQLite DB 생성, 4개 테이블 확인

- [x] **1-6. Pydantic 스키마 정의**
  - [x] `backend/app/models/schemas.py` 생성
  - [x] `ChatRequest` (session_id?, message)
  - [x] `ChatResponse` (run_id, session_id)
  - [x] `AgentInfo` (name, role_preset, status)
  - [x] `RunStatus` (status, progress?, response?, mode?, agents?)
  - [x] `AgentMessageOut` (id, sender, role_preset, content, status, created_at)
  - [x] `AgentMessagesResponse` (messages, has_more)
  - [x] `SessionOut` (id, title?, created_at, updated_at)
  - [x] `UserMessageOut` (id, role, content, mode?, created_at)
  - [x] `SessionDetail` (extends SessionOut + messages)
  - [x] `AgentPlan` (role, task)
  - [x] `ClassificationResult` (mode, reason, agents, user_status_message?)

- [x] **1-7. 프론트엔드 프로젝트 초기화**
  - [x] Vite + React + TypeScript 프로젝트 생성
  - [x] TailwindCSS 설정 (`@tailwindcss/vite`)
  - [x] `vite.config.ts` — API 프록시 설정 (→ localhost:8000)
  - [x] `frontend/package.json` 의존성 정의
  - [x] `cd frontend && npm run dev` → `:5173` 접속 확인

- [x] **1-8. Claude CLI 설치 확인 스크립트**
  - [x] `justfile`의 `setup` 태스크에 `which claude` 검사
  - [x] 미설치 시 경고 메시지 출력

### Sprint 1 완료 검증

- [x] `just setup` → 백엔드·프론트엔드 의존성 설치 + Claude CLI 확인
- [x] `just backend` → FastAPI Swagger UI 접속
- [x] `just frontend` → Vite 개발 서버 접속
- [x] `just migrate` → SQLite DB 생성, 4개 테이블 존재 확인
- [x] `ruff check .` → 린트 에러 없음

---

## Sprint 2: CLI 서비스 및 핵심 인프라 ✅

> **목표**: Claude CLI 래퍼, Global Execution Lock, 세션 서비스 구현
> **PRD 참조**: ADR-004, ADR-006, F-001a~F-001c

### 태스크

- [x] **2-1. CLI 서비스 구현 (Popen + 라인 스트리밍)** `[Plan: High]`
  - 파일: `backend/app/services/cli_service.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_cli_service.py` 생성
    - [x] `test_call_claude_sync_returns_output` — mock Popen → stdout 라인 수신 확인
    - [x] `test_call_claude_sync_calls_on_line_callback` — on_line 콜백 호출 확인
    - [x] `test_call_claude_sync_timeout` — 타임아웃 초과 시 프로세스 종료 확인
    - [x] `test_call_claude_streaming_async` — asyncio.to_thread 래퍼 동작 확인
    - [x] `test_line_buffer_flusher_append_and_flush` — 버퍼 추가 + flush 동작
    - [x] `test_line_buffer_flusher_thread_safety` — 다수 스레드 동시 append + flush 시 데이터 무결성
    - [x] `test_line_buffer_flusher_stop_flushes_remaining` — stop 시 잔여 데이터 flush
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `_call_claude_sync(system_prompt, user_message, on_line, **kwargs)` 동기 함수
      - [x] `subprocess.Popen` 으로 Claude CLI 실행
      - [x] `start_new_session=True` 로 새 프로세스 그룹 생성
      - [x] `bufsize=1` 라인 버퍼링 설정
      - [x] `stdout` 라인별 루프 → `on_line` 콜백 호출
      - [x] `--output-format json` 옵션 지원 (kwargs)
      - [x] `_current_proc` 에 Popen 객체 보관
      - [x] 환경변수 `CLAUDE_CLI_PATH`, `CLAUDE_CLI_TIMEOUT` 참조
      - [x] 타임아웃 초과 시 프로세스 종료 + 에러 반환
    - [x] `call_claude_streaming(system_prompt, user_message, on_line, **kwargs)` 비동기 함수
      - [x] `asyncio.to_thread(_call_claude_sync, ...)` 래퍼
      - [x] `_cli_lock` (Global Lock) 내부에서 실행
    - [x] `LineBufferFlusher` 클래스
      - [x] `_lock: threading.Lock` — 버퍼 동시 접근 보호
      - [x] `_buffer: list[str]` — 인메모리 라인 버퍼
      - [x] `_timer: threading.Timer` — 0.5초 간격 반복 flush
      - [x] `append(line)` — Lock 획득 → 버퍼에 라인 추가
      - [x] `flush()` — Lock 획득 → 버퍼 스왑(교체+초기화) → Lock 해제 → 스왑된 데이터를 동기 `sqlite3`로 DB UPDATE
      - [x] `start()` — Timer 시작
      - [x] `stop()` — 잔여 버퍼 최종 flush + Timer 정지
      - [ ] DB 기록은 동기 `sqlite3` 별도 connection 사용 (aiosqlite 아님)
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_cli_service.py -v` → 전체 PASS
  - 🔵 **REFACTOR**
    - [x] 코드 정리, `ruff check` 통과

- [x] **2-2. Global Execution Lock 구현** `[Plan: High]`
  - 파일: `backend/app/services/cli_service.py` 내
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_cli_service.py`에 추가
    - [x] `test_global_lock_sequential_execution` — 동시 2개 호출 시 순차 실행 확인
    - [x] `test_cancel_current_kills_process_group` — cancel 시 os.killpg 호출 확인
    - [x] `test_cancel_current_handles_no_process` — 프로세스 없을 때 안전 처리
    - [x] 테스트 실행 → FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `_cli_lock = asyncio.Lock()` 모듈 레벨 정의
    - [x] `_current_proc: subprocess.Popen | None = None` 모듈 레벨 정의
    - [x] `execute_with_lock(coro)` — Lock 획득 후 코루틴 실행
    - [x] `cancel_current()` — `os.killpg(pgid, SIGTERM)` 프로세스 그룹 종료
    - [x] `ProcessLookupError` 예외 처리
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_cli_service.py -v` → 전체 PASS (기존 테스트 포함)
  - 🔵 **REFACTOR**
    - [x] 코드 정리

- [x] **2-3. JSON 파싱 폴백 체인 구현** `[Plan: High]`
  - 파일: `backend/app/services/classification.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_classification.py` 생성
    - [x] `test_parse_valid_json` — 정상 JSON → Pydantic 검증 통과
    - [x] `test_parse_json_with_prefix` — `"Here is the result: {...}"` → 정규식 추출 성공
    - [x] `test_parse_invalid_text_falls_back_to_solo` — `"I cannot classify"` → Solo 폴백
    - [x] `test_parse_missing_fields_tries_regex` — 필수 필드 누락 → Pydantic 실패 → 정규식
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `parse_classification(raw_output: str) -> ClassificationResult`
    - [x] 1단계 (F-001a): `json.loads()` → Pydantic 검증
    - [x] 2단계 (F-001b): `re.finditer()` 정규식 추출 (개별 JSON 블록 순차 시도)
    - [x] 3단계 (F-001c): Solo 폴백 반환
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_classification.py -v` → 전체 PASS
  - 🔵 **REFACTOR**
    - [x] 코드 정리

- [x] **2-4. 세션 CRUD 서비스** `[Plan: Medium]`
  - 파일: `backend/app/services/session_service.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_session_service.py` 생성
    - [x] `tests/conftest.py` — 테스트용 인메모리 DB fixture 생성
    - [x] `test_create_session` — 세션 생성 → id, created_at 존재
    - [x] `test_list_sessions` — 복수 생성 → 최신순 목록 반환
    - [x] `test_get_session` — 존재하는 세션 조회 성공
    - [x] `test_get_session_not_found` — 없는 세션 → 예외/None
    - [x] `test_get_session_with_messages` — 메시지 포함 상세 조회
    - [x] `test_create_user_message` — 메시지 저장 → 세션에 연결
    - [x] `test_create_run` — Run 생성 → status="queued"
    - [x] `test_update_run_status` — 상태 업데이트 확인
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `create_session(db) -> Session`
    - [x] `get_session(db, session_id) -> Session`
    - [x] `list_sessions(db) -> list[Session]`
    - [x] `get_session_with_messages(db, session_id) -> SessionDetail`
    - [x] `create_user_message(db, session_id, role, content, mode?)`
    - [x] `create_run(db, session_id, user_message_id) -> Run`
    - [x] `update_run_status(db, run_id, status, **fields)`
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_session_service.py -v` → 전체 PASS
  - 🔵 **REFACTOR**
    - [x] 코드 정리

- [x] **2-5. 설정 관리 (pydantic-settings)** `[Plan: Skip]`
  - 파일: `backend/app/config.py`
  - [x] `Settings` 클래스 (pydantic-settings `BaseSettings`)
  - [x] `claude_cli_path`, `claude_cli_timeout` 설정
  - [x] `max_sub_agents` 설정
  - [x] `session_ttl_seconds`, `db_path` 설정
  - [x] `cors_origins` → `cors_origin_list` 프로퍼티
  - [x] `database_url` 프로퍼티 (sqlite+aiosqlite)
  - [x] `.env` 파일 로드 확인

### Sprint 2 테스트 게이트 ✅

> **다음 Sprint 진입 조건: 아래 전체 통과 필수**

- [x] `pytest tests/test_cli_service.py -v` → 전체 PASS (10개)
- [x] `pytest tests/test_classification.py -v` → 전체 PASS (4개)
- [x] `pytest tests/test_session_service.py -v` → 전체 PASS (8개)
- [x] `pytest -v` → **전체 테스트 스위트 100% PASS (22개)**
- [x] `ruff check .` → 린트 에러 없음
- [x] ✅ Sprint 3 진입 가능

---

## Sprint 3: Solo 모드 End-to-End ✅

> **목표**: 사용자 메시지 → Reader Solo 응답 → DB 저장 전체 흐름
> **PRD 참조**: F-001~F-002, F-005, ADR-005
> **진입 조건**: Sprint 2 테스트 게이트 100% 통과

### 태스크

- [x] **3-1. Reader Agent 구현 (분류 + Solo 응답)** `[Plan: High]`
  - 파일: `backend/app/agents/reader.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_reader.py` 생성
    - [x] `test_classify_returns_solo` — Solo 분류 입력 → mode="solo" 반환 (CLI mock)
    - [x] `test_classify_returns_team` — Team 분류 입력 → mode="team" 반환 (CLI mock)
    - [x] `test_solo_respond_returns_text` — Solo 응답 CLI 호출 → 텍스트 반환
    - [x] `test_process_message_solo_flow` — 전체 흐름: thinking → solo → done
    - [x] `test_process_message_error_handling` — CLI 에러 시 runs status → "error"
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `ReaderAgent` 클래스 정의
    - [x] `process_message(session_id, user_message, run_id)` — 전체 흐름
    - [x] `_classify(user_message) -> ClassificationResult`
    - [x] `_solo_respond(user_message) -> str`
    - [x] 에러 시 runs status → `"error"`
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_reader.py -v` → 전체 PASS
  - 🔵 **REFACTOR**

- [x] **3-2~3-3. REST 엔드포인트 구현 (chat, runs)** `[Plan: High]`
  - 파일: `backend/app/routers/chat.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_api_chat.py` 생성
    - [x] `test_post_chat_returns_run_id` — POST → run_id + session_id 반환
    - [x] `test_post_chat_creates_session_if_missing` — session_id 생략 시 자동 생성
    - [x] `test_post_chat_returns_fast` — 응답 시간 < 1.0s (BackgroundTask)
    - [x] `test_get_run_status` — GET → RunStatus 스키마 반환
    - [x] `test_get_run_status_not_found` — 없는 run_id → 404
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `POST /api/chat` — 세션 생성 + 메시지 저장 + run 생성 + BackgroundTask 등록
    - [x] `GET /api/runs/{run_id}` — 상태 조회
    - [x] `_run_reader_agent()` — 자체 DB 세션으로 백그라운드 실행
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_api_chat.py -v` → 전체 PASS

- [x] **3-4. 세션 엔드포인트 구현 (목록·상세·생성)** `[Plan: Medium]`
  - 파일: `backend/app/routers/sessions.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_api_sessions.py` 생성
    - [x] `test_list_sessions` — GET → 세션 목록 반환
    - [x] `test_create_session` — POST → 새 세션 생성 + 반환 (201)
    - [x] `test_get_session_detail` — GET → 메시지 포함 상세 반환
    - [x] `test_get_session_not_found` — 없는 session_id → 404
    - [x] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `GET /api/sessions` — 목록 조회
    - [x] `POST /api/sessions` — 생성 (status_code=201)
    - [x] `GET /api/sessions/{session_id}` — 상세 조회
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_api_sessions.py -v` → 전체 PASS

- [x] **3-4-a. 세션 제목 자동 생성** `[Plan: Skip]`
  - 파일: `backend/app/services/session_service.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_session_service.py`에 `test_auto_title_generation` 추가
    - [x] 첫 user 메시지 저장 시 `session.title`이 `null`이면 앞 30자로 설정되는지 확인
    - [x] 30자 초과 메시지 → `"…"` 붙는지 확인
    - [x] 이미 `title`이 있는 경우 → 덮어쓰지 않는지 확인
    - [x] 테스트 실행 → FAIL 확인
  - 🟢 **GREEN — 구현**
    - [x] `session_service.py`의 `create_user_message()` 에서 `role == "user"` + `session.title is None`이면 `message[:30] + ("…" if len(message) > 30 else "")` 로 세션 제목 자동 설정
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_session_service.py -v` → 전체 PASS

- [x] **3-5. 백그라운드 실행 관리 (BackgroundTasks)** `[Plan: High]`
  - 파일: `reader.py` + `chat.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [x] `tests/test_background.py` 생성
    - [x] `test_background_task_updates_run_status` — 상태 변화 순서 검증
    - [x] `test_background_task_acquires_lock` — Lock 획득 후 실행 확인
  - 🟢 **GREEN — 구현**
    - [x] BackgroundTasks 연동
    - [x] runs 상태 실시간 업데이트
  - 🟢 **테스트 통과 확인**
    - [x] `pytest tests/test_background.py -v` → 전체 PASS

- [x] **3-6. 통합 테스트: Solo E2E** `[Plan: Skip]`
  - 파일: `tests/test_solo_e2e.py`
  - [x] httpx `AsyncClient` 로 FastAPI 전체 흐름 테스트
  - [x] `test_solo_e2e_full_flow` — POST → 폴링 → done + response 확인
  - [x] `test_solo_e2e_session_history` — 대화 히스토리 확인
  - [x] `test_solo_e2e_json_fallback` — 비정상 CLI 출력 → Solo 응답 성공
  - [x] `pytest tests/test_solo_e2e.py -v` → 전체 PASS

### Sprint 3 테스트 게이트 ✅

> **다음 Sprint 진입 조건: 아래 전체 통과 필수**

- [x] `pytest -v` → **전체 테스트 스위트 44/44 PASS** (Sprint 2 22개 + Sprint 3 22개)
- [x] `ruff check .` → 린트 에러 없음
- [x] `POST /api/chat` → `run_id` 즉시 반환 (< 100ms) 확인 (수동) — 41ms 측정
- [x] Solo 모드: 메시지 → 15초 이내 최종 응답 확인 (수동) — 약 2초 측정
- [x] `tests/test_background.py` — BackgroundTasks + Lock 연동
- [x] `tests/test_solo_e2e.py` — Solo 모드 전체 흐름 httpx
- [x] ✅ Sprint 4 진입 가능 (수동 검증 제외)

---

## Sprint 4: 프론트엔드 기초 및 Solo UI ✅

> **목표**: React 앱 구조, User Channel UI, 폴링 훅, Solo 모드 완전 동작
> **PRD 참조**: Section 10 (UI/UX 명세), F-020~F-023
> **진입 조건**: Sprint 3 테스트 게이트 100% 통과

### 태스크

- [x] **4-1. API 타입 및 클라이언트** `[Plan: Skip]`
  - [x] `frontend/src/types/api.ts` — TypeScript 인터페이스 정의
    - [x] `ChatRequest`, `ChatResponse`
    - [x] `RunStatusType`, `RunStatus`, `AgentInfo`
    - [x] `AgentMessage`, `AgentMessagesResponse`
    - [x] `Session`, `UserMessage`, `SessionDetail`
  - [x] `frontend/src/lib/api.ts` — API 클라이언트
    - [x] `get<T>()`, `post<T>()` 헬퍼 함수
    - [x] `api.chat()`, `api.getRunStatus()`, `api.getAgentMessages()`
    - [x] `api.cancelRun()`, `api.getSessions()`, `api.createSession()`, `api.getSession()`
    - [x] 에러 처리 (`res.ok` 체크)

- [x] **4-2. `useRunPolling` 훅 구현** `[Plan: Medium]`
  - 파일: `frontend/src/hooks/useRunPolling.ts`
  - [x] `useRunPolling(runId, callbacks?)` 시그니처 (onDone/onError/onCancelled 콜백)
  - [x] 2초 + 지터(±300ms) 간격 폴링: `interval = 2000 + Math.random() * 600 - 300`
  - [x] `api.getRunStatus(runId)` 호출
  - [x] 터미널 상태 (`done` | `error` | `cancelled`) 도달 시 폴링 정지 + 콜백 호출
  - [x] 반환: `RunStatus` (runId null이면 DEFAULT_STATE 반환)
  - [x] cleanup: 컴포넌트 언마운트 시 폴링 정지

- [x] **4-3. `useSession` 훅 구현** `[Plan: Medium]`
  - 파일: `frontend/src/hooks/useSession.ts`
  - [x] 현재 활성 세션 + 메시지 상태 관리
  - [x] `api.getSessions()` 로 세션 목록 로드 (마운트 시)
  - [x] `api.createSession()` 로 새 세션 생성
  - [x] `api.getSession(id)` 로 세션 전환 + 히스토리 로드
  - [x] `addMessage`, `setCurrentSessionFromChat`, `refreshSessions` 유틸 제공

- [x] **4-4. 레이아웃 (2패널) 구현** `[Plan: Skip]`
  - 파일: `frontend/src/App.tsx`
  - [x] 좌측: Session Sidebar (접기/펼치기)
  - [x] 중앙: User Channel (메시지 목록 + 입력)
  - [x] 우측: Agent Channel (420px 고정폭)
  - [x] 실제 컴포넌트 연결 (useSession 훅 통합)
  - [x] 세션 전환 시 UserChannel key prop으로 상태 자동 reset

- [x] **4-5. User Channel 컴포넌트 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/UserChannel/index.tsx`
  - [x] 메시지 목록 렌더링 (MessageBubble 사용)
  - [x] 메시지 입력 영역 (input + Enter 전송)
  - [x] 전송 버튼 → `api.chat()` 호출 → `runId` 수신
  - [x] `useRunPolling(runId, callbacks)` 연동
  - [x] `done` 시 응답을 새 메시지로 추가 (콜백 기반)
  - [x] 자동 스크롤 (최신 메시지로)
  - [x] 전송 중 입력 비활성화

- [x] **4-6. StatusBadge 컴포넌트 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/UserChannel/StatusBadge.tsx`
  - [x] 9개 상태별 표시: queued, thinking, solo, delegating, working, integrating, done, error, cancelled
  - [x] 상태별 색상 + pulse 애니메이션 (진행 중 상태)
  - [x] `progress` 표시 지원

- [x] **4-7. 마크다운 렌더링 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/UserChannel/MessageBubble.tsx`
  - [x] `react-markdown` + `rehype-highlight` 설치 및 적용
  - [x] `highlight.js/styles/github.css` 임포트
  - [x] Reader 응답 메시지에 마크다운 렌더링 (h1~h3, ul/ol, pre/code, blockquote 등)
  - [x] 코드 블록 구문 하이라이팅
  - [x] User 메시지는 일반 텍스트 렌더링
  - [x] 역할별 (user/reader) 버블 스타일 분기

- [x] **4-8. 세션 사이드바 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/SessionList/index.tsx`
  - [x] 세션 목록 표시 (최신순, 날짜 포맷)
  - [x] 세션 클릭 → 전환 (히스토리 로드)
  - [x] "새 세션" 버튼 → `api.createSession()` 호출
  - [x] 현재 활성 세션 하이라이트

- [x] **4-9. Agent Channel 대기 상태 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/AgentChannel/index.tsx`
  - [x] Solo/null 모드 시 "대기 중" 플레이스홀더 표시
  - [x] Team 모드 시 전환 준비 (Sprint 6에서 완성)

### Sprint 4 테스트 게이트 ✅ (마일스톤 M1)

> **다음 Sprint 진입 조건: 아래 전체 통과 필수**

- [x] `cd backend && uv run pytest -v` → **백엔드 전체 테스트 100% PASS (47개)**
- [x] `cd frontend && npx tsc --noEmit` → **TypeScript 타입 체크 통과**
- [x] `cd frontend && npm run lint` → **ESLint 에러 없음**
- [x] `cd frontend && npm run build` → **프로덕션 빌드 성공**
- [x] 수동 검증: 메시지 입력 → 전송 → StatusBadge 상태 변화 → Reader 응답 표시 — thinking→solo→done 상태 전이 확인 (11초)
- [x] 수동 검증: 마크다운·코드 블록 렌더링 정상 — `#`, `##`, ` ``` `, `` ` `` 포함 응답 수신 확인
- [x] 수동 검증: 세션 목록·전환·새 세션 생성·히스토리 복원 — 10개 세션, limit/offset 페이지네이션, 히스토리 2개 메시지 복원 확인
- [x] ✅ Sprint 5 진입 가능

---

## Sprint 5: Team 모드 백엔드 ⬜

> **목표**: Sub-Agent 프리셋, Context Assembler, Team 오케스트레이션 전체 구현
> **PRD 참조**: F-003~F-004, F-010~F-014, ADR-001, ADR-006
> **진입 조건**: Sprint 4 테스트 게이트 100% 통과

### 태스크

- [ ] **5-1. Sub-Agent 기반 클래스 구현** `[Plan: High]`
  - 파일: `backend/app/agents/sub_agent.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_sub_agent.py` 생성
    - [ ] `test_sub_agent_execute` — CLI mock → 태스크 결과 반환
    - [ ] `test_sub_agent_build_prompt_without_context` — context 없음 → task만 포함
    - [ ] `test_sub_agent_build_prompt_with_context` — context 존재 → 이전 결과 주입
    - [ ] `test_sub_agent_calls_on_line` — 실행 중 on_line 콜백 호출 확인
    - [ ] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [ ] `SubAgent.__init__(name, role_preset, system_prompt)`
    - [ ] `execute(task, context, on_line) -> str`
    - [ ] `_build_prompt(task, context)`
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_sub_agent.py -v` → 전체 PASS

- [ ] **5-2. 5개 프리셋 시스템 프롬프트 구현** `[Plan: Medium]`
  - 파일: `backend/app/agents/presets/*.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_presets.py` 생성
    - [ ] `test_researcher_prompt_exists` — SYSTEM_PROMPT 문자열 존재 + 필수 키워드 포함
    - [ ] `test_coder_prompt_exists`
    - [ ] `test_reviewer_prompt_exists`
    - [ ] `test_writer_prompt_exists`
    - [ ] `test_planner_prompt_exists`
    - [ ] `test_all_presets_non_empty` — 5개 모두 빈 문자열 아님
  - 🟢 **GREEN — 구현**
    - [ ] `presets/__init__.py` — 패키지 초기화 파일 생성 (빈 파일)
    - [ ] `researcher.py` — 상세 시스템 프롬프트
    - [ ] `coder.py` — 상세 시스템 프롬프트
    - [ ] `reviewer.py` — 상세 시스템 프롬프트
    - [ ] `writer.py` — 상세 시스템 프롬프트
    - [ ] `planner.py` — 상세 시스템 프롬프트
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_presets.py -v` → 전체 PASS

- [ ] **5-3. Context Assembler 구현** `[Plan: High]`
  - 파일: `backend/app/agents/reader.py` 내
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_context_assembler.py` 생성
    - [ ] `test_assemble_empty_results` — 결과 없음 → None 반환
    - [ ] `test_assemble_short_results` — 3000자 미만 → 원문 그대로 포함
    - [ ] `test_assemble_long_result_triggers_summary` — 3000자 초과 → 요약 CLI 호출 확인
    - [ ] `test_assemble_format` — `[Agent이름 결과]:\n내용` 포맷 검증
    - [ ] `test_second_agent_receives_first_result` — 2번째 프롬프트에 1번째 결과 포함
    - [ ] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [ ] `CONTEXT_CHAR_LIMIT = 3000`
    - [ ] `_assemble_context(results)`
    - [ ] `_summarize_for_context(agent_name, content)`
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_context_assembler.py -v` → 전체 PASS

- [ ] **5-4. Team 오케스트레이션 루프 구현** `[Plan: High]`
  - 파일: `backend/app/agents/reader.py` 내
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_team_orchestration.py` 생성
    - [ ] `test_team_execute_status_flow` — 상태 변화: delegating → working → integrating → done
    - [ ] `test_team_execute_runs_agents_sequentially` — 2~3 Agent 순차 실행
    - [ ] `test_team_execute_integrates_results` — 통합 CLI 호출 + 최종 응답 저장
    - [ ] `test_team_execute_records_agent_messages` — agent_messages DB 기록
    - [ ] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [ ] `_team_execute(classification, user_message, run_id)`
    - [ ] `_create_agent(agent_plan)` — SubAgent 생성
    - [ ] `_integrate_results(user_message, results)` — 통합 CLI 호출
    - [ ] `LineBufferFlusher` 연동 (배치 DB 쓰기)
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_team_orchestration.py -v` → 전체 PASS

- [ ] **5-5. Agent Channel DB 기록 구현** `[Plan: Medium]`
  - 파일: `backend/app/services/session_service.py` 확장
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_session_service.py`에 추가
    - [ ] `test_create_agent_message` — 레코드 생성 확인
    - [ ] `test_update_agent_message_content` — 중간 출력 누적 업데이트
    - [ ] `test_update_agent_message_status` — 상태 변경 확인
  - 🟢 **GREEN — 구현**
    - [ ] `create_agent_message(db, session_id, run_id, sender, role_preset)`
    - [ ] `update_agent_message_content(db, msg_id, content)`
    - [ ] `update_agent_message_status(db, msg_id, status)`
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_session_service.py -v` → 전체 PASS (기존 + 신규)

- [ ] **5-6. `GET /api/runs/{run_id}/agent-messages` 구현** `[Plan: Medium]`
  - 파일: `backend/app/routers/chat.py` 확장
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_api_chat.py`에 추가
    - [ ] `test_get_agent_messages` — agent_messages 조회 반환
    - [ ] `test_get_agent_messages_empty` — 메시지 없음 → 빈 배열
    - [ ] `test_get_agent_messages_includes_working` — working 상태 중간 출력 포함
  - 🟢 **GREEN — 구현**
    - [ ] `GET /api/runs/{run_id}/agent-messages` 엔드포인트
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_api_chat.py -v` → 전체 PASS

- [ ] **5-7. 취소 기능 구현** `[Plan: High]`
  - 파일: `backend/app/routers/chat.py` + `cli_service.py`
  - 🔴 **RED — 테스트 먼저 작성**
    - [ ] `tests/test_cancel.py` 생성
    - [ ] `test_cancel_solo_run` — Solo 실행 중 취소 → cancelled
    - [ ] `test_cancel_team_run` — Team 실행 중 취소 → 부분 결과 보존
    - [ ] `test_cancel_invalid_status` — done 상태에서 취소 → 무시
    - [ ] `test_cancel_kills_process_group` — os.killpg 호출 확인
    - [ ] 테스트 실행 → 전부 FAIL 확인
  - 🟢 **GREEN — 구현**
    - [ ] `POST /api/runs/{run_id}/cancel` 엔드포인트
    - [ ] 취소 가능 상태 검증
    - [ ] `cancel_current()` 호출
    - [ ] Team 중단 플래그 설정
  - 🟢 **테스트 통과 확인**
    - [ ] `pytest tests/test_cancel.py -v` → 전체 PASS

- [ ] **5-8. 통합 테스트: Team E2E** `[Plan: Skip]`
  - 파일: `tests/test_team_e2e.py`
  - [ ] `test_team_e2e_full_flow` — POST → 폴링 → delegating → working → integrating → done
  - [ ] `test_team_e2e_agent_messages` — 각 Agent 중간 출력 확인
  - [ ] `test_team_e2e_cancel` — Team 실행 중 취소
  - [ ] `pytest tests/test_team_e2e.py -v` → 전체 PASS

### Sprint 5 테스트 게이트 🚧

> **다음 Sprint 진입 조건: 아래 전체 통과 필수**

- [ ] `pytest -v` → **전체 테스트 스위트 100% PASS** (Sprint 2~5 테스트 모두)
- [ ] `ruff check .` → 린트 에러 없음
- [ ] Team E2E: 분류 → 순차 실행 → 통합 → done 전체 흐름
- [ ] Context Assembler: 3000자 초과 요약 포함 흐름 확인
- [ ] 취소: Solo + Team 취소 정상 동작
- [ ] 🚫 1개라도 실패 시 Sprint 6 진입 금지

---

## Sprint 6: Team UI 및 마무리 ⬜

> **목표**: Agent Channel UI, 취소 버튼, 내보내기, 에러 처리, 전체 통합 검증
> **PRD 참조**: F-024, F-030~F-035, Section 12 성공 기준
> **진입 조건**: Sprint 5 테스트 게이트 100% 통과

### 태스크

- [ ] **6-1. `useAgentPolling` 훅 구현** `[Plan: Medium]`
  - 파일: `frontend/src/hooks/useAgentPolling.ts`
  - [ ] `useAgentPolling(runId, mode, isVisible)` 시그니처
  - [ ] `mode`가 `"team"`이 아니면 폴링 비활성
  - [ ] `isVisible`이 `false` (Agent Channel 탭 비활성)이면 폴링 일시 중지
  - [ ] 탭 재활성화 시 즉시 1회 fetch 후 정상 폴링 재개
  - [ ] 2초 + 지터(±300ms) 간격: `interval = 2000 + Math.random() * 600 - 300`
  - [ ] `api.getAgentMessages(runId)` 호출
  - [ ] `has_more=false` 이고 run이 `done` → 폴링 중단
  - [ ] 반환: `{ messages: AgentMessage[], isPolling: boolean }`
  - [ ] cleanup: 언마운트 시 폴링 정지

- [ ] **6-2. Agent Channel 메시지 목록 구현** `[Plan: Skip]`
  - 파일: `frontend/src/components/AgentChannel/index.tsx`
  - [ ] `useAgentPolling` 훅 연동
  - [ ] 메시지 목록 렌더링 (`AgentMessage` 컴포넌트 사용)
  - [ ] Solo 모드 → "대기 중" 표시 유지
  - [ ] Team 모드 → 메시지 목록 표시로 전환
  - [ ] AgentStatusBar 표시 영역

- [ ] **6-3. Agent Channel 중간 출력 표시** `[Plan: Skip]`
  - 파일: `frontend/src/components/AgentChannel/AgentMessage.tsx`
  - [ ] 헤더: 발신자 이름 + 역할 프리셋 배지 + 타임스탬프
  - [ ] 본문: content 표시 (working 상태 → 타이핑 애니메이션)
  - [ ] 상태: working(⏳) / done(✅) / error(❌) / cancelled
  - [ ] 폴링마다 content 증가 시 자동 스크롤
  - [ ] 새 content 부분 하이라이팅 (선택)

- [ ] **6-4. Team 상태 표시 (User Channel)** `[Plan: Medium]`
  - 파일: `frontend/src/components/UserChannel/StatusBadge.tsx` 확장
  - [ ] Team 모드 상태 흐름: delegating → working(N/M) → integrating → done
  - [ ] `working` 상태에서 진행률 표시 (`"2/3"` 형식)
  - [ ] 각 상태별 색상/아이콘 차별화

- [ ] **6-5. 취소 버튼 구현** `[Plan: Medium]`
  - 파일: `frontend/src/components/UserChannel/index.tsx`
  - [ ] 실행 중 (queued~integrating) → 전송 버튼을 [취소 ✕] 버튼으로 대체
  - [ ] 클릭 → `api.cancelRun(runId)` 호출
  - [ ] 응답 수신 → StatusBadge `"cancelled"` 표시
  - [ ] Team 모드: `"N개 중 M개 완료 후 취소됨"` 메시지 표시
  - [ ] 취소 후 입력 영역 다시 활성화

- [ ] **6-6. Agent Channel 요약 표시** `[Plan: Skip]`
  - 파일: `frontend/src/components/AgentChannel/AgentStatusBar.tsx`
  - [ ] 팀 요약 정보: `"3 Agents · 소요 시간: 8분"` 형식
  - [ ] 전체 Agent 수, 완료 수, 진행 상태
  - [ ] 총 소요 시간 (run started_at ~ finished_at)

- [ ] **6-7. Agent Channel 내보내기** `[Plan: Skip]`
  - 파일: `frontend/src/components/AgentChannel/index.tsx`
  - [ ] 내보내기 버튼 (Agent Channel 헤더)
  - [ ] 텍스트 형식 다운로드 (발신자 + 내용)
  - [ ] JSON 형식 다운로드 (전체 메시지 배열)
  - [ ] Blob + `URL.createObjectURL` 로 브라우저 다운로드 트리거

- [ ] **6-8. 에러 처리 UI** `[Plan: Skip]`
  - 파일: 관련 컴포넌트 전반
  - [ ] CLI 실패 시 User Channel에 에러 메시지 표시
  - [ ] 타임아웃 발생 시 사용자 안내 메시지
  - [ ] 네트워크 에러 (API 호출 실패) 처리
  - [ ] 에러 상태 시 "다시 시도" 유도 UI
  - [ ] Agent Channel: Agent 에러 상태 시각적 표시 (❌)

- [ ] **6-9. 전체 통합 테스트** `[Plan: Skip]`
  - [ ] **수동 E2E 테스트** (브라우저에서 전체 흐름)
    - [ ] Solo: 메시지 입력 → 응답 → 마크다운 렌더링 확인
    - [ ] Team: 복잡한 요청 → Agent Channel 중간 출력 → 통합 응답
    - [ ] 취소: Solo/Team 각각 취소 동작 확인
    - [ ] 세션: 생성 → 전환 → 히스토리 복원
    - [ ] 에러: CLI 경로 잘못 → 에러 메시지 표시 확인
  - [ ] **분류 정확도 테스트** (20개 테스트 케이스)
    - [ ] Solo 8개 케이스 통과
    - [ ] Team 12개 케이스 통과
    - [ ] 목표: 20개 중 18개 이상 정확

### Sprint 6 최종 테스트 게이트 🚧 (마일스톤 M2)

> **Phase 1 완료 조건: 아래 전부 통과 필수**

- [ ] `cd backend && uv run pytest -v` → **백엔드 전체 테스트 100% PASS**
- [ ] `cd frontend && npx tsc --noEmit` → **TypeScript 타입 체크 통과**
- [ ] `cd frontend && npm run lint` → **ESLint 에러 없음**
- [ ] `cd frontend && npm run build` → **프로덕션 빌드 성공**
- [ ] `cd backend && uv run ruff check .` → **린트 에러 없음**
- [ ] **분류 정확도**: 테스트 케이스 20개 중 18개 이상 정확
- [ ] **Solo 응답**: 15초 이내
- [ ] **Team 진행 표시**: 폴링 2초 이내에 상태 업데이트
- [ ] **Agent Channel**: 모든 Sub-Agent 결과 누락 없이 표시
- [ ] **세션 복원**: 새로고침 후 이전 대화 완전 복원
- [ ] **취소**: Solo/Team 모두 정상 동작
- [ ] **에러 처리**: CLI 실패 시 사용자에게 명확한 메시지
- [ ] 🚫 1개라도 실패 시 Phase 1 릴리스 불가

---

## 테스트 파일 현황

| 상태 | 파일 | Sprint | 테스트 대상 | TDD 순서 |
|:----:|------|:------:|-----------|:--------:|
| ✅ | `tests/conftest.py` | 2 | CLI mock fixture, 인메모리 DB fixture | 가장 먼저 |
| ✅ | `tests/test_cli_service.py` | 2 | CLI 호출 mock, 타임아웃, Global Lock, LineBufferFlusher | RED 먼저 |
| ✅ | `tests/test_classification.py` | 2 | JSON 파싱 3단계 폴백 (4 케이스) | RED 먼저 |
| ✅ | `tests/test_session_service.py` | 2 | 세션 CRUD + Agent 메시지 CRUD | RED 먼저 |
| ✅ | `tests/test_reader.py` | 3 | Reader Agent: 분류, Solo 응답, 에러 처리 | RED 먼저 |
| ✅ | `tests/test_api_chat.py` | 3 | POST /api/chat, GET /api/runs, agent-messages | RED 먼저 |
| ✅ | `tests/test_api_sessions.py` | 3 | 세션 API 엔드포인트 CRUD | RED 먼저 |
| ✅ | `tests/test_background.py` | 3 | BackgroundTasks + Lock 연동 | RED 먼저 |
| ✅ | `tests/test_solo_e2e.py` | 3 | Solo 모드 전체 흐름 (httpx) | RED 먼저 |
| ⬜ | `tests/test_sub_agent.py` | 5 | SubAgent 클래스 실행, 프롬프트 빌드 | RED 먼저 |
| ⬜ | `tests/test_presets.py` | 5 | 5개 프리셋 시스템 프롬프트 존재 검증 | RED 먼저 |
| ⬜ | `tests/test_context_assembler.py` | 5 | 프롬프트 체이닝, 3000자 요약 | RED 먼저 |
| ⬜ | `tests/test_team_orchestration.py` | 5 | Team 오케스트레이션 상태 흐름 | RED 먼저 |
| ⬜ | `tests/test_cancel.py` | 5 | Solo·Team 취소 | RED 먼저 |
| ⬜ | `tests/test_team_e2e.py` | 5 | Team 모드 전체 흐름 (httpx) | RED 먼저 |

---

## 참고

### 범례

| 기호 | 의미 |
|:----:|------|
| ✅ / `[x]` | 완료 |
| 🔧 | 진행 중 (일부 하위 태스크 완료) |
| ⬜ / `[ ]` | 미착수 |
| ❌ | 차단됨 / 이슈 발생 |
| 🚫 | 테스트 게이트 차단 (다음 Sprint 진입 불가) |
| 🔴 | RED — 실패하는 테스트 작성 단계 |
| 🟢 | GREEN — 테스트 통과하는 구현 단계 |
| 🔵 | REFACTOR — 코드 개선 단계 |

### TDD 워크플로우 요약

```
각 태스크마다:
  1. 🔴 테스트 파일 생성 + 테스트 함수 작성
  2. 🔴 pytest 실행 → 전부 FAIL 확인 (이 단계가 없으면 TDD가 아님)
  3. 🟢 최소한의 구현 코드 작성
  4. 🟢 pytest 실행 → 전부 PASS 확인
  5. 🔵 리팩토링 (테스트 통과 유지)
  6. 🟢 pytest 전체 재실행 → 회귀 없음 확인

Sprint 완료 시:
  7. pytest -v (전체) → 100% PASS
  8. ruff check . → 린트 에러 없음
  9. ✅ 다음 Sprint 진입 가능
```

### 상태 업데이트 규칙

1. 태스크 완료 시 `[ ]` → `[x]` 로 변경
2. Sprint 헤더의 상태 아이콘 갱신 (⬜ → 🔧 → ✅)
3. 전체 진행 요약 테이블의 `태스크 진행` + `테스트 게이트` 컬럼 갱신
4. 테스트 게이트 통과 시 해당 행 상태 갱신
5. 마일스톤 달성 시 해당 행 상태 갱신
