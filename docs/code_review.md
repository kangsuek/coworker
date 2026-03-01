# Sprint 5 코드 리뷰

> **작성일**: 2026-03-01
> **대상**: Sprint 5 Team 모드 백엔드 구현
> **범례**: 🔴 Critical · 🟠 Major · 🟡 Minor

---

## 요약

| 심각도 | 건수 |
|--------|:----:|
| 🔴 Critical | 2 |
| 🟠 Major | 8 |
| 🟡 Minor | 4 |

**전체 평가**: 기능적으로 개발 계획 대비 95% 완성이나, Critical 2건 및 Major 8건 해결 권장.

---

## 🔴 Critical

### C-1. flush_callback에서 동기 sqlite3 연결 반복 생성 — DB 경합 위험

**위치**: `backend/app/agents/reader.py:157-173`

현재 구현:
```python
def flush_callback(lines: list[str]) -> None:
    accumulated.extend(lines)
    content = "".join(accumulated)
    try:
        conn = sqlite3.connect(settings.db_path)          # 매 flush마다 새 연결 생성
        conn.execute("UPDATE agent_messages ...", ...)
        conn.commit()
        conn.close()
    except Exception:
        pass                                               # 에러 무시 — 손실 감지 불가
```

문제:
- 0.5초마다 sqlite3 연결 생성/해제 → 연결 오버헤드
- WAL 모드 설정(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`)이 **새 연결에 적용 안 됨**
- Sub-Agent 여러 개 동시 실행 시 동시 sqlite3 write 경합 가능
- 예외 무시(`pass`) → DB 쓰기 실패를 알 수 없음

**개선 방법**:
```python
def flush_callback(lines: list[str]) -> None:
    accumulated.extend(lines)
    content = "".join(accumulated)
    try:
        conn = sqlite3.connect(settings.db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("UPDATE agent_messages SET content = ? WHERE id = ?",
                     (content, agent_msg.id))
        conn.commit()
        conn.close()
    except Exception:
        logger.warning("LineBufferFlusher DB 쓰기 실패: msg_id=%s", agent_msg.id)
```

---

### C-2. cancel_current()의 Race Condition — Popen 생성 전 취소 요청 처리 불완전

**위치**: `backend/app/services/cli_service.py:26-27, 68-75`

시나리오:
1. call_claude_streaming 호출 → Lock 획득 대기
2. 다른 코루틴에서 cancel_current() 호출 → `_is_cancelled = True`
3. Lock 획득 → Popen 생성 시작
4. Popen 생성 완료 후 `_current_proc = proc` 할당
5. 그 사이 cancel_current()에서 `_current_proc`이 None → killpg 미호출

타이밍 윈도우: Popen 생성 직후 ~ `_current_proc = proc` 할당 직전

**개선 방법**: `_is_cancelled` 체크를 Popen 직후(할당 전)에 즉시 수행하도록 이동 (현재 위치도 Popen 직후이나, 할당 전 체크는 되어 있음). 또는 `threading.Lock`으로 `_current_proc` 할당 원자화.

---

## 🟠 Major

### M-1. 함수 내부 import — reader.py:151

**위치**: `backend/app/agents/reader.py:151-153`

```python
# _team_execute() 함수 내부에서 import
import sqlite3
from app.config import settings
```

모듈 상단에 위치해야 함. 함수 내부 import는 매 호출 시 모듈 캐시를 조회하는 오버헤드 발생.

**수정**: 파일 상단으로 이동.

---

### M-2. accumulated 버퍼와 LineBufferFlusher._buffer 이중 누적

**위치**: `backend/app/agents/reader.py:155-173`

```python
accumulated: list[str] = []          # 외부 closure

def flush_callback(lines: list[str]) -> None:
    accumulated.extend(lines)         # 누적 1번
    content = "".join(accumulated)
    ...

flusher = LineBufferFlusher(flush_callback)  # flusher._buffer 별도 존재 → 누적 2번
```

LineBufferFlusher `_buffer`와 `accumulated`가 별도로 존재해 데이터가 두 군데 유지됨. 메모리 낭비, 추적 어려움.

**개선 방법**: `accumulated`를 제거하고 content를 LineBufferFlusher에서 직접 관리하거나, 최종 result를 `flusher.stop()` 이후 DB에 한 번만 저장.

---

### M-3. cancel_current()의 에러 처리 불충분

**위치**: `backend/app/services/cli_service.py:130-133`

```python
try:
    os.killpg(os.getpgid(_current_proc.pid), signal.SIGTERM)
except ProcessLookupError:
    pass
# os.getpgid() 실패 시 OSError도 발생 가능
```

`ProcessLookupError` 외에도 `OSError`가 발생할 수 있음. 예: 이미 좀비 프로세스 상태.

**수정**:
```python
except (ProcessLookupError, OSError):
    pass
```

---

### M-4. ReaderAgent가 너무 많은 책임을 보유

**위치**: `backend/app/agents/reader.py` (전체, 235줄)

단일 파일에 다음 책임이 집중:
1. Solo/Team 분류
2. Solo 응답 생성
3. Team 오케스트레이션 루프
4. Context Assembler (조립 + 요약)
5. 결과 통합
6. LineBufferFlusher 생성 및 콜백 구현
7. Agent Channel DB 기록
8. 에러 처리 및 에러 메시지 JSON 파싱

**제안**: Sprint 6 이후 리팩토링 대상으로 표시. 최소 `context_assembler.py` 분리 권장.

---

### M-5. CONTEXT_CHAR_LIMIT 하드코딩

**위치**: `backend/app/agents/reader.py:28`

```python
CONTEXT_CHAR_LIMIT = 3000
```

런타임 조정 불가. Agent 결과물 크기가 크거나 Claude 모델 변경 시 조정 필요.

**수정**:
```python
import os
CONTEXT_CHAR_LIMIT = int(os.getenv("CONTEXT_CHAR_LIMIT", "3000"))
```

---

### M-6. Team 오케스트레이션 중 Sub-Agent Exception 처리 없음

**위치**: `backend/app/agents/reader.py:131-191`

`_team_execute()` 내부에서 개별 Agent 실행 실패 시:
- 전체 Team 실행이 상위 `process_message()`의 except로 catch
- 완료된 Sub-Agent 결과는 보존되지 않음
- agent_messages의 status가 `working`으로 남음

**개선 방법**:
```python
try:
    result = await execute_with_lock(agent.execute(...))
except Exception as e:
    await update_agent_message_status(self.db, agent_msg.id, "error")
    raise  # 또는 continue + 부분 결과 보존
```

---

### M-7. Context Assembler 경계값 테스트 부재

**위치**: `backend/tests/test_context_assembler.py`

현재 테스트:
- `"A" * 3001` — 3001자 초과 케이스만 있음

누락:
- 정확히 3000자 → 원문 포함 (요약 미호출)
- 정확히 3001자 → 요약 호출 (경계)
- 요약 실패 시 fallback 동작

**추가 필요**:
```python
async def test_assemble_exactly_3000_chars(db):
    """정확히 3000자 → 요약 미호출"""
    result = "A" * 3000
    results = {"Agent-A": result}
    with patch.object(agent, "_summarize_for_context") as mock_s:
        context = await agent._assemble_context(results)
    mock_s.assert_not_called()
    assert result in context
```

---

### M-8. Team 오케스트레이션 Exception 경로 테스트 미흡

**위치**: `backend/tests/test_team_orchestration.py`

모든 테스트가 성공 경로만 검증. 누락된 시나리오:
1. Sub-Agent 실행 중 Exception → Team 전체 중단 동작
2. `_integrate_results` CLI 실패 → 에러 상태 전환
3. `update_agent_message_status` DB 실패

---

## 🟡 Minor

### m-1. reader.py:94-109 — 에러 메시지 JSON 파싱 로직 복잡

**위치**: `backend/app/agents/reader.py:94-109`

오류 발생 시 에러 메시지에서 JSON 추출 시도하는 로직이 복잡. 가독성이 낮으며 팀 모드에서도 동일 로직이 필요할 수 있음.

**개선 방법**: `_extract_error_message(error: Exception) -> str` 헬퍼 함수로 추출.

---

### m-2. Agent 이름 중복 가능성

**위치**: `backend/app/agents/reader.py:199`

```python
name=f"{agent_plan.role}-A"  # 모든 Agent가 "-A" 접미사
```

Team에 동일 역할이 2개 있을 경우 (예: Coder × 2) 이름이 중복됨.

**수정**:
```python
name=f"{agent_plan.role}-{i + 1}"  # i는 enumerate 인덱스
```

---

### m-3. flush_callback 예외 무시 (`pass`)

**위치**: `backend/app/agents/reader.py:172-173`

예외를 로그 없이 무시하면 운영 환경에서 DB 쓰기 실패를 감지할 수 없음.

**수정**:
```python
except Exception:
    logger.warning("LineBufferFlusher DB 쓰기 실패: msg_id=%s", agent_msg.id, exc_info=True)
```

---

### m-4. Cancel race condition 테스트 미흡

**위치**: `backend/tests/test_cancel.py`

현재 테스트는 상태 변경만 확인. 누락:
1. Team 실행 도중 중간 Agent 취소 → 부분 결과 보존 확인
2. 이미 done인 run에 cancel 후 agent_messages 상태 확인

---

## 액션 아이템

### Sprint 5 완료 전 조치 권장

- [x] C-1: flush_callback에 `PRAGMA` 설정 및 에러 로깅 추가
- [x] C-2: cancel_current() race condition 방어 강화 (`OSError` 추가)
- [x] M-1: `import sqlite3`, `from app.config import settings`를 파일 상단으로 이동
- [x] M-3: `except (ProcessLookupError, OSError)` 수정
- [x] m-3: flush_callback 예외 로깅 추가

### Sprint 6 진입 전 조치 권장

- [x] M-7: Context Assembler 경계값 테스트 추가 (3000, 3001자)
- [x] M-8: Team 오케스트레이션 Exception 경로 테스트 추가
- [x] M-6: Sub-Agent 실패 시 agent_messages.status → "error" 처리
- [x] m-2: Agent 이름 중복 방지 (f"{role}-{i+1}")

### 리팩토링 (Sprint 6 이후)

- [ ] M-4: reader.py에서 Context Assembler 분리
- [ ] M-5: CONTEXT_CHAR_LIMIT 환경변수화
- [ ] M-2: accumulated 이중 버퍼 제거
