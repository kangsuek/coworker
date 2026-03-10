# Coworker 버그 수정 작업 계획

research.md 조사 결과를 바탕으로 아직 수정되지 않은 버그를 우선순위별로 정리.

---

## 이미 완료된 항목 (코드 확인)
- [x] BUG-SUBAGENT-01: SubAgent `file_paths` 파라미터 누락 → 수정 완료
- [x] BUG-DB-01: PendingRollbackError → `await self.db.rollback()` 추가 완료
- [x] BUG-SSE-01: SSE 캐시 race condition → terminal 상태 체크 추가 완료
- [x] BUG-CLI-RESP: Claude CLI 빈 응답 → `chunks` fallback 완료
- [x] BUG-SESSION-SWITCH: 세션 전환 시 runId 유실 → `sessionRunIdRef` 완료
- [x] BUG-CANCEL-01: `_cancelled_runs` 누수 → `finally`에서 `discard()` 완료
- [x] BUG-APP-01: Claude CLI PATH 보강 → `/opt/homebrew/bin` 등 추가 완료
- [x] BUG-GEMINI-02: Gemini CLI PATH 보강 → 동일하게 추가 완료
- [x] BUG-SESSION-01: 세션 삭제 시 활성 run 미취소 → `cancel_current()` 호출 완료
- [x] BUG-MEMORY-01: SSE 큐 메모리 누수 → 30초 TTL 자동 정리 완료
- [x] BUG-SSE-02: SSE 무한 재연결 → `MAX_RECONNECT_ATTEMPTS=8` 완료

---

## Phase 1 — 코드 품질 / 즉시 수정 (Quick Fix)

### T01: `model_to_use` 중복 OR 표현식 수정 (BUG-PARSE-01) ✅
- **파일**: `backend/app/agents/reader.py`
- **내용**: `self.session_model or self.session_model or ""` → `self.session_model or ""` (copy-paste 버그, 6곳)
- [x] reader.py line 232, 446, 613, 707, 730, 742 수정 완료

### T02: `on_line` 콜백 예외 격리 (BUG-STREAM-02) ✅
- **파일**: `backend/app/services/cli_service.py`, `gemini_cli.py`
- **내용**: `on_line(chunk)` 호출을 try-except로 감싸 콜백 예외가 전체 스트림을 중단하지 않도록
- [x] cli_service.py on_line 호출 보호 완료
- [x] gemini_cli.py on_line 호출 보호 완료

### T03: NDJSON 파싱 실패 DEBUG 로깅 추가 (BUG-NDJSON-01) ✅
- **파일**: `backend/app/services/cli_service.py`, `gemini_cli.py`
- **내용**: `except json.JSONDecodeError: continue` → `logger.debug(...)` 추가
- [x] cli_service.py 파싱 실패 로깅 완료
- [x] gemini_cli.py 파싱 실패 로깅 완료

### T04: model 문자열 strip 처리 (BUG-MODEL-01) ✅
- **파일**: `backend/app/services/cli_service.py`, `gemini_cli.py`
- **내용**: `kwargs.get("model", "")` → `(kwargs.get("model") or "").strip()` 로 공백 모델명 방어
- [x] cli_service.py model.strip() 완료
- [x] gemini_cli.py model.strip() 완료

---

## Phase 2 — 서버 안정성

### T05: 서버 종료 시 활성 run 취소 및 상태 정리 (BUG-SHUTDOWN-01) ✅
- **파일**: `backend/app/main.py`
- **내용**: lifespan shutdown에서 ACTIVE 상태 run 전체 조회 → `cancel_current()` 후 DB를 "cancelled"로 업데이트
- [x] main.py lifespan shutdown 로직 추가 완료

---

## Phase 3 — Thread Safety

### T06: `_active_procs` threading.Lock 추가 (BUG-THREAD-01) ✅
- **파일**: `backend/app/services/cli_service.py`, `gemini_cli.py`
- **내용**: `_call_claude_sync`는 `asyncio.to_thread()`로 스레드 풀에서 실행됨. `_active_procs` dict 접근에 `threading.Lock` 추가
- [x] `_active_procs_lock = threading.Lock()` 추가 완료
- [x] `_active_procs` 읽기/쓰기 모두 lock 보호 완료 (cli_service.py)
- [x] gemini_cli.py 동일하게 적용 완료

---

## Phase 4 — 진단 개선

### T07: 취소 후 on_line 콜백 차단 (BUG-CANCEL-02) ✅
- **파일**: `backend/app/services/cli_service.py`, `gemini_cli.py`
- **내용**: 취소 감지 후 on_line을 None으로 교체하여 파이프 버퍼 잔여 데이터 DB 오염 방지
- [x] cli_service.py 취소 후 on_line = None 완료
- [x] gemini_cli.py 취소 후 on_line = None 완료

### T08: 완료 후 커밋 ✅
- [x] git commit 완료

---

## 참고: 추후 개선 사항 (이번 배치 제외)
- BUG-PYINST-01: PyInstaller hidden imports (server.spec) — 패키징 테스트 시 적용
- BUG-CORS-01: CORS 동적 포트 — 프로덕션 배포 시 검토
- BUG-DB-02: BackgroundTask 독립 DB 세션 — 리팩터링 필요
