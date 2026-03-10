# Coworker CLI 실행 흐름 심층 버그 조사 보고서

**작성일**: 2026-03-10
**조사 범위**: App(PyInstaller 패키징) vs Web 환경 동작 차이, 전체 CLI 실행 흐름
**총 발견 버그**: 31건 (Critical 3, High 10, Medium 15, Low 1, Info 2)

---

## 조사 배경

App 환경(DMG/EXE 패키징)에서 Claude/Gemini CLI 응답이 돌아오지 않거나, 취소된 작업이 계속 실행되거나, 팀 모드 에이전트가 "working" 상태에서 멈추는 문제들이 다수 보고되었다. 이에 CLI 실행 전체 흐름을 코드 수준에서 분석하여 잠재적 버그를 모두 식별한다.

---

## 실행 흐름 요약

```
사용자 입력
  └→ POST /runs/start (reader.py: process_message)
       └→ BackgroundTasks.add_task(reader._run_background)
            └→ reader._run_background
                 ├─ [Solo] call_claude_streaming() / gemini_cli.stream_generate()
                 │    └→ asyncio.to_thread(_call_claude_sync)
                 │         └→ subprocess.Popen(claude --output-format stream-json ...)
                 │              └→ NDJSON 라인 파싱 → on_line 콜백 → LineBufferFlusher
                 │                   └→ DB upsert (0.5s 배치)
                 └─ [Team] asyncio.gather(*[agent.execute() for agent in agents])
                      └→ SubAgent.execute() → LLMProvider.stream_generate()
```

---

## 버그 목록

### CRITICAL (즉시 수정 필요)

#### BUG-APP-01: PATH 환경변수 누락 (App 환경 CLI 실행 불가)
- **파일**: `backend/app/services/cli_service.py:75-76`
- **심각도**: Critical
- **현상**: DMG/EXE 앱에서 `claude`/`node` 바이너리를 찾지 못해 `FileNotFoundError` 발생
- **원인**: PyInstaller 앱은 PATH가 `/usr/bin:/bin`만 설정됨. `/usr/local/bin`, `/opt/homebrew/bin` 미포함
- **현재 코드**:
  ```python
  _extra = "/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin"
  child_env["PATH"] = _extra + ":" + child_env.get("PATH", "")
  ```
- **문제**: `settings_service.get("claude_cli_path")`로 full path를 사용자가 지정해도, PATH 보강이 Popen 직전에만 적용됨. `gemini_cli.py`에는 동일한 PATH 보강 로직이 없음
- **수정 방향**: `gemini_cli.py`에도 동일한 PATH 보강 로직 추가; `settings_service`에서 cli_path를 가져올 때 존재 여부 검증 추가

#### BUG-CANCEL-01: `_cancelled_runs` 세트 영구 누적 (메모리 누수)
- **파일**: `backend/app/services/cli_service.py:29, 230-231`
- **심각도**: Critical
- **현상**: 취소된 run_id가 `_cancelled_runs` 세트에 영원히 남아 메모리 누수 발생. 더 심각하게, 취소된 run_id와 동일한 ID가 재사용되면 새 실행이 즉시 취소됨
- **원인**: `cancel_current(run_id)`에서 `_cancelled_runs.add(run_id)`는 하지만 완료/정리 시 제거하지 않음
- **수정 방향**: `_call_claude_sync` finally 블록에서 `_cancelled_runs.discard(run_id)` 호출

#### BUG-PARSE-01: `model_to_use` 중복 OR 표현식 (Python 3.10 이전 호환성)
- **파일**: `backend/app/agents/reader.py` (model_to_use 결정 로직)
- **심각도**: Critical
- **현상**: `model_to_use = run.model or settings.default_model or ""` 형태인데, `run.model`이 빈 문자열 `""`이면 falsy로 평가되어 `settings.default_model`로 fallback됨. 하지만 사용자가 의도적으로 빈 모델을 설정한 경우 예상치 못한 동작
- **추가**: team 모드에서 `provider`를 결정하는 로직이 solo와 다를 수 있음 — 두 경로에서 동일한 provider/model 선택 로직 사용 여부 확인 필요

---

### HIGH (우선 수정 권장)

#### BUG-DB-01: 예외 핸들러 내 PendingRollbackError
- **파일**: `backend/app/agents/reader.py`
- **심각도**: High
- **현상**: agent 실행 중 예외 발생 시, 예외 핸들러에서 동일 DB 세션으로 상태 업데이트 시도 → `PendingRollbackError` → 상태가 "working"에서 변경되지 않아 UI가 영원히 로딩 중
- **원인**: SQLAlchemy async 세션은 예외 후 rollback 없이는 재사용 불가
- **수정**: 예외 핸들러 진입 시 즉시 `await self.db.rollback()` 호출 (이미 수정됨)

#### BUG-CORS-01: CORS 동적 포트 미지원
- **파일**: `backend/app/main.py`
- **심각도**: High
- **현상**: App 환경에서 포트가 동적으로 변경될 때 CORS allow_origins가 고정 포트를 사용하면 API 요청 차단
- **현재 코드**: `allow_origins=["http://localhost:5173", "http://localhost:8080"]` 등 하드코딩
- **수정 방향**: `allow_origins=["*"]` (개발용) 또는 `settings`에서 동적으로 읽기

#### BUG-PYINST-01: PyInstaller hidden imports 누락
- **파일**: `build_dmg/server.spec`
- **심각도**: High
- **현상**: 패키징된 앱에서 특정 Python 모듈 import 실패 (`ModuleNotFoundError`)
- **원인**: PyInstaller가 동적 import를 감지하지 못함. SQLAlchemy dialect, asyncio transport 등
- **수정 방향**: `hiddenimports`에 `sqlalchemy.dialects.sqlite`, `asyncio`, `uvicorn.lifespan.on` 등 추가

#### BUG-TEAM-01: 팀 모드 zombie 프로세스
- **파일**: `backend/app/agents/reader.py` (team 실행 로직)
- **심각도**: High
- **현상**: `asyncio.gather()`로 실행된 팀 에이전트 중 하나가 취소되면 나머지 에이전트의 `asyncio.to_thread` 스레드가 계속 실행됨
- **원인**: `asyncio.to_thread()`로 실행된 blocking 함수는 `Task.cancel()`로 취소할 수 없음. 스레드는 계속 실행되고 이벤트 루프만 신경 씀
- **수정 방향**: `_cancelled_runs`에 run_id 추가 후 스레드 내부 루프에서 체크하도록 함 (이미 구현됨); gather에 `return_exceptions=True` 추가 검토

#### BUG-SESSION-01: 세션 삭제 시 실행 중인 run 미취소
- **파일**: `backend/app/routers/` (session delete 엔드포인트)
- **심각도**: High
- **현상**: 사용자가 세션 삭제 시 해당 세션의 활성 run이 취소되지 않고 백그라운드에서 계속 실행
- **수정 방향**: 세션 삭제 전 해당 세션의 active run_id 조회 후 `cancel_current(run_id)` 호출

#### BUG-GEMINI-01: Gemini CLI 응답 없을 때 fallback 부재
- **파일**: `backend/app/services/llm/gemini_cli.py`
- **심각도**: High
- **현상**: Gemini CLI `result` 이벤트 없을 때 빈 문자열 반환
- **원인**: Claude CLI와 달리 delta 청크 누적 fallback 로직 없음
- **수정 방향**: Claude CLI와 동일하게 `chunks` 누적 후 `return final_result or "".join(chunks)` 패턴 적용

#### BUG-PARSE-02: 분류 서비스 output_json=False로 실행
- **파일**: `backend/app/services/classification.py`
- **심각도**: High
- **현상**: 분류 서비스가 `output_json=True`를 전달하지 않으면 stream-json 모드로 실행되어 불필요한 스트리밍 오버헤드 + JSON 파싱 실패
- **현재 코드**: `call_claude_streaming(system, user_msg)` (output_json 미전달)
- **수정 방향**: `call_claude_streaming(..., output_json=True)` 명시

#### BUG-SSE-01: SSE 캐시 race condition
- **파일**: `backend/app/services/stream_service.py`
- **심각도**: High
- **현상**: 두 클라이언트가 동시에 동일 run_id를 구독할 때, 하나가 unsubscribe하면서 다른 하나의 캐시도 삭제될 수 있음
- **원인**: `unsubscribe` 시 큐가 비면 캐시 삭제 → 아직 연결 중인 다른 클라이언트가 reconnect 시 캐시 없음
- **수정 방향**: 이미 수정됨 (terminal 상태일 때만 캐시 삭제)

#### BUG-THREAD-01: `_active_procs` dict thread safety
- **파일**: `backend/app/services/cli_service.py:27`
- **심각도**: High
- **현상**: `_active_procs` dict가 여러 스레드에서 동시에 수정될 때 race condition 가능
- **원인**: `asyncio.to_thread()`로 `_call_claude_sync`가 별도 스레드에서 실행되므로 dict 접근이 thread-safe하지 않음
- **수정 방향**: `threading.Lock` 또는 `collections.defaultdict` + atomic 연산 사용

#### BUG-SHUTDOWN-01: 서버 종료 시 BackgroundTask 미완료
- **파일**: `backend/app/main.py` (lifespan 또는 shutdown 핸들러)
- **심각도**: High
- **현상**: 서버 종료 시 실행 중인 BackgroundTask가 강제 종료되어 DB 상태가 "working"으로 남음
- **수정 방향**: lifespan의 shutdown에서 `cancel_current()` 호출 후 활성 run 상태를 "cancelled"로 업데이트

---

### MEDIUM

#### BUG-SUBAGENT-01: SubAgent.execute() file_paths 파라미터 누락
- **파일**: `backend/app/agents/sub_agent.py`
- **심각도**: Medium (이미 수정됨)
- **현상**: `file_paths` 파라미터가 없어 `TypeError` 발생
- **수정**: `file_paths: list[str] | None = None` 추가 및 `stream_generate`에 전달 (완료)

#### BUG-STREAM-01: LineBufferFlusher stop 후 미전송 청크 유실
- **파일**: `backend/app/services/cli_service.py:312-322`
- **심각도**: Medium
- **현상**: `stop()` 호출 시 task cancel 후 final flush를 하지만, task가 cancel되면 finally의 flush가 실행되지 않을 수 있음
- **분석**: `_run_loop`의 `except CancelledError: pass` 후 `finally: await self.flush()`는 실행됨. 하지만 `stop()`에서 task cancel 후 `await self._task`가 CancelledError를 잡고, 그 후 `await self.flush()`를 다시 호출하므로 이중 flush 발생 가능 (중복 DB 쓰기)

#### BUG-STREAM-02: on_line 콜백 예외 시 전체 스트림 중단
- **파일**: `backend/app/services/cli_service.py:150-151`
- **심각도**: Medium
- **현상**: `on_line(chunk)` 콜백에서 예외 발생 시 try 블록 밖에서 캐치되어 전체 Popen 루프 중단
- **수정 방향**: `on_line` 호출을 try-except로 감싸기

#### BUG-ENV-01: CLAUDECODE 환경변수 제거가 항상 동작하지 않음
- **파일**: `backend/app/services/cli_service.py:73`
- **심각도**: Medium
- **현상**: `child_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}` 방어 코드 있음. 하지만 Claude CLI가 다른 환경변수(CLAUDE_SESSION 등)도 확인할 수 있음
- **수정 방향**: `CLAUDE_`로 시작하는 Claude Code 관련 환경변수 전체 제거 검토

#### BUG-CWD-01: cwd="/tmp"의 부작용
- **파일**: `backend/app/services/cli_service.py:91`
- **심각도**: Medium
- **현상**: `cwd="/tmp"`로 CLAUDE.md 오염 방지는 하지만, Claude CLI가 /tmp 기준으로 상대경로 파일 접근. `--file` 옵션의 절대경로는 문제없지만 상대경로 사용 시 오류
- **현재 상태**: `file_paths`는 절대경로이므로 큰 문제 없음

#### BUG-TIMEOUT-01: proc.wait(timeout) 후 프로세스 좀비
- **파일**: `backend/app/services/cli_service.py:155`
- **심각도**: Medium
- **현상**: `proc.wait(timeout=timeout)` TimeoutExpired 시 SIGTERM 후 `proc.wait()` 재호출. 하지만 자식 프로세스 그룹의 모든 프로세스가 종료될 때까지 blocking
- **수정 방향**: SIGTERM 후 일정 시간 후 SIGKILL 추가

#### BUG-DB-02: DB 세션 스코프 문제
- **파일**: `backend/app/agents/reader.py`
- **심각도**: Medium
- **현상**: BackgroundTask에서 사용하는 DB 세션이 request scope이면 요청 완료 후 세션이 닫힘. 팀 모드 에이전트 실행 중 DB 세션 만료 가능
- **수정 방향**: BackgroundTask에서는 별도 `AsyncSession` 생성하여 독립적 생명주기 관리

#### BUG-MODEL-01: 모델명 빈 문자열로 Claude CLI 호출
- **파일**: `backend/app/services/cli_service.py:61-62`
- **심각도**: Medium
- **현상**: `model=""`이면 `cmd.extend(["--model", ""])` 미실행. 하지만 `model`이 `" "` (공백)이면 `--model " "` 전달되어 CLI 오류
- **수정 방향**: `model.strip()` 후 비어있을 때만 추가

#### BUG-NDJSON-01: NDJSON 파싱 오류 시 silent 무시
- **파일**: `backend/app/services/cli_service.py:138-139`
- **심각도**: Medium
- **현상**: JSON 파싱 실패 시 `continue`로 무시. Claude CLI가 오류 메시지를 JSON이 아닌 plain text로 출력할 때 오류 정보 유실
- **수정 방향**: 파싱 실패한 라인 DEBUG 레벨로 로깅

#### BUG-RUN-01: run_id 생성 충돌 가능성
- **파일**: `backend/app/` (run_id 생성 위치)
- **심각도**: Medium
- **현상**: `uuid4()`로 생성하므로 충돌 가능성 극히 낮으나, 테스트 환경에서 고정 seed 사용 시 문제 가능

#### BUG-CANCEL-02: 취소 후 on_line 콜백 계속 호출
- **파일**: `backend/app/services/cli_service.py:117-123`
- **심각도**: Medium
- **현상**: 취소 감지 후 SIGTERM 전송하고 `break`하지만, 이미 파이프 버퍼에 있는 데이터는 `on_line`으로 전달됨. 취소 후에도 일부 청크가 DB에 쓰여질 수 있음
- **수정 방향**: 취소 감지 후 `on_line`을 None으로 교체하는 패턴

#### BUG-GEMINI-02: Gemini CLI PATH 보강 누락
- **파일**: `backend/app/services/llm/gemini_cli.py`
- **심각도**: Medium
- **현상**: Claude CLI에는 `/opt/homebrew/bin` 등 PATH 보강이 있지만 Gemini CLI에는 없어 App 환경에서 `gemini` 바이너리를 못 찾을 수 있음
- **수정 방향**: `cli_service.py`의 PATH 보강 로직을 공통 함수로 추출하여 양쪽에 적용

#### BUG-SSE-02: EventSource 재연결 무한 루프
- **파일**: `frontend/src/App.tsx` (SSE 구독 로직)
- **심각도**: Medium
- **현상**: SSE 연결 실패 시 브라우저가 자동 재연결하는데, 서버가 404를 반환하면 (run_id 없음) 계속 재연결 시도
- **수정 방향**: `onerror` 핸들러에서 특정 오류 코드에 대해 `eventSource.close()` 호출

#### BUG-MEMORY-01: 완료된 run SSE 큐 메모리 누수
- **파일**: `backend/app/services/stream_service.py`
- **심각도**: Medium
- **현상**: 클라이언트가 정상적으로 unsubscribe하지 않으면 (네트워크 단절 등) SSE 큐가 `queues` dict에 남아있을 수 있음
- **수정 방향**: run 완료 후 일정 시간(예: 30초) 후 자동으로 해당 run_id 큐 정리

#### BUG-FILE-01: 업로드된 임시 파일 미정리
- **파일**: `backend/app/routers/` (파일 업로드 처리)
- **심각도**: Medium
- **현상**: CLI 실행에 사용된 임시 파일이 완료 후 삭제되지 않을 수 있음
- **수정 방향**: finally 블록에서 임시 파일 삭제

---

### LOW

#### BUG-LOG-01: 민감 정보 로그 노출
- **파일**: `backend/app/services/cli_service.py:70`
- **심각도**: Low
- **현상**: `logger.debug("Claude CLI 시작: run_id=%s, model=%s, output_json=%s", ...)` — run_id와 모델명은 문제없으나, system_prompt나 user_message 전체를 로깅하는 경우 민감 정보 노출 가능
- **현재 상태**: 현재 전체 메시지는 로깅하지 않으므로 양호

---

### INFO (참고사항)

#### INFO-01: `start_new_session=True`의 의미
- **파일**: `backend/app/services/cli_service.py:88`
- **설명**: `start_new_session=True`는 새 프로세스 세션을 만들어 `os.killpg()`로 자식 프로세스 그룹 전체를 SIGTERM할 수 있게 함. 의도적이고 올바른 설계

#### INFO-02: `stderr=subprocess.STDOUT` 선택
- **파일**: `backend/app/services/cli_service.py:86`
- **설명**: stderr를 stdout에 합쳐 파이프 버퍼 포화로 인한 deadlock 방지. 올바른 설계이나, stderr 오류 메시지가 NDJSON 파싱 시 JSON parse 오류로 무시됨 (BUG-NDJSON-01과 연관)

---

## 이미 수정된 버그

| 버그 ID | 설명 | 수정 방법 |
|---------|------|-----------|
| BUG-SUBAGENT-01 | SubAgent file_paths 파라미터 누락 | execute()에 file_paths 추가 |
| BUG-DB-01 | PendingRollbackError | 예외 핸들러 진입 시 rollback() 추가 |
| BUG-SSE-01 | SSE 캐시 race condition | terminal 상태일 때만 캐시 삭제 |
| BUG-CLI-RESP | Claude CLI 빈 응답 | chunks fallback 추가 |
| BUG-SESSION-SWITCH | 세션 전환 시 runId 유실 | sessionRunIdRef Map 추가 |

---

## 수정 우선순위 권장

### Phase 1 (즉시)
1. **BUG-APP-01** — Gemini CLI PATH 보강 추가
2. **BUG-CANCEL-01** — `_cancelled_runs` finally 블록에서 정리
3. **BUG-PARSE-02** — 분류 서비스 `output_json=True` 명시
4. **BUG-GEMINI-02** — Gemini CLI PATH 보강 (BUG-APP-01과 함께)

### Phase 2 (단기)
5. **BUG-DB-02** — BackgroundTask 독립 DB 세션
6. **BUG-SHUTDOWN-01** — 서버 종료 시 run 상태 정리
7. **BUG-THREAD-01** — `_active_procs` thread safety
8. **BUG-SESSION-01** — 세션 삭제 시 run 취소

### Phase 3 (중기)
9. **BUG-STREAM-02** — on_line 콜백 예외 격리
10. **BUG-NDJSON-01** — 파싱 실패 라인 로깅
11. **BUG-MEMORY-01** — SSE 큐 자동 정리
12. **BUG-FILE-01** — 임시 파일 정리

---

## 결론

App 환경에서 CLI가 동작하지 않는 가장 큰 원인은 **BUG-APP-01/BUG-GEMINI-02 (PATH 문제)**와 **BUG-PYINST-01 (PyInstaller hidden imports)**이다. 팀 모드 멈춤 현상의 주요 원인은 **BUG-DB-01 (PendingRollbackError)**과 **BUG-SUBAGENT-01 (파라미터 누락)**으로, 두 버그 모두 이미 수정되었다. 취소 관련 이상 동작의 원인은 **BUG-CANCEL-01 (_cancelled_runs 누수)**이다.
