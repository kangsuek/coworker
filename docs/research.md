# 세션 삭제 기능 버그 조사 보고서

조사 범위: 세션 삭제 아이콘 클릭 → 백엔드 삭제 → 프론트엔드 상태 갱신 전 흐름
조사 일자: 2026-03-02

---

## 조사 대상 파일

| 레이어 | 파일 |
|--------|------|
| Frontend UI | `frontend/src/components/SessionList/index.tsx` |
| Frontend Hook | `frontend/src/hooks/useSession.ts` |
| Frontend App | `frontend/src/App.tsx` |
| Frontend Polling | `frontend/src/hooks/useAgentPolling.ts`, `useRunPolling.ts` |
| Frontend Channel | `frontend/src/components/UserChannel/index.tsx` |
| Backend Router | `backend/app/routers/sessions.py` |
| Backend Service | `backend/app/services/session_service.py` |
| Backend Agent | `backend/app/agents/reader.py` |
| Backend CLI | `backend/app/services/cli_service.py` |
| DB Model | `backend/app/models/db.py` |

---

## 버그 목록

### Bug 1 — [Critical] 실행 중인 세션 삭제 시 백그라운드 태스크가 고아(orphan) 레코드를 생성

**위치**
- `backend/app/routers/sessions.py:34-39`
- `backend/app/services/session_service.py:26-36`
- `backend/app/agents/reader.py:83-129`

**재현 시나리오**

1. 사용자가 메시지를 전송해 Run이 시작됨 (`POST /api/chat` → status: `thinking` / `solo` / `working`)
2. 사용자가 해당 세션의 🗑 버튼 클릭
3. `DELETE /api/sessions/{session_id}` 호출 → `delete_session()` 실행
4. DB에서 runs, agent_messages, user_messages, session 순서로 모두 삭제 완료
5. 하지만 `_run_reader_agent` 백그라운드 태스크는 **여전히 실행 중**
6. 태스크가 완료 또는 예외 발생 시 다음 코드 실행:

```python
# reader.py:90-91 (Solo 완료 시)
await create_user_message(self.db, session_id, "reader", text, mode="solo")
await update_run_status(self.db, run_id, "done", response=text, mode="solo")

# reader.py:126-129 (예외 발생 시)
await create_user_message(
    self.db, session_id, "reader", f"⚠️ 오류 발생: {error_msg}", mode="solo"
)
await update_run_status(self.db, run_id, "error", response=error_msg)
```

7. `update_run_status`: run이 이미 삭제됐으므로 `db.get(Run, run_id)` → `None` 반환, 조용히 no-op
8. **`create_user_message`**: session이 이미 삭제됐지만 `db.py`에 `PRAGMA foreign_keys=ON`이 없어 FK 위반 검사 없이 **user_messages 테이블에 고아 레코드가 삽입됨**

**DB 스키마 확인**

```python
# db.py:26-30 — foreign_keys PRAGMA 없음!
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    # PRAGMA foreign_keys=ON; ← 없음
```

**근본 원인 2가지**

1. `session_service.delete_session()`에서 `cancel_current()`를 호출하지 않아 CLI 프로세스가 고아로 계속 실행됨
2. SQLite FK 강제(`PRAGMA foreign_keys=ON`)가 꺼져 있어 삭제된 session_id 참조가 방어되지 않음

**영향**
- DB에 영구 고아 레코드 축적 (쿼리 불가, 정리 불가)
- Team 모드에서는 `flush_callback`(별도 스레드)도 삭제된 `agent_msg.id`로 `UPDATE agent_messages` 반복 시도 → 0 rows affected로 조용히 손실

---

### Bug 2 — [High] 세션 삭제 후 App.tsx가 currentRunId / currentMode를 리셋하지 않아 폴링이 지속됨

**위치**
- `frontend/src/App.tsx:135`

**문제 코드**

```tsx
// App.tsx:135 — session.deleteSession만 전달, Run 상태 리셋 없음
onDeleteSession={session.deleteSession}
```

**비교: 세션 전환·생성은 Run 상태를 리셋함**

```tsx
// App.tsx:110-120
const handleSwitchSession = (id: string) => {
  setCurrentRunId(null)   // ✅ 리셋
  setCurrentMode(null)    // ✅ 리셋
  session.switchSession(id)
}

const handleCreateSession = () => {
  setCurrentRunId(null)   // ✅ 리셋
  setCurrentMode(null)    // ✅ 리셋
  session.createSession()
}
```

**결과 흐름**

1. Run이 진행 중인 세션(예: `currentRunId = "run-xyz"`, `currentMode = "team"`)을 삭제
2. `useSession.deleteSession()` 내부에서 다른 세션으로 전환 또는 새 세션 생성
3. 그러나 `currentRunId = "run-xyz"`, `currentMode = "team"` 은 그대로 유지
4. `App.tsx:99-103`의 `useAgentPolling(currentRunId, currentMode, true)` 가 삭제된 run_id로 계속 폴링
5. `GET /api/runs/run-xyz/agent-messages` → **404** → `useAgentPolling`의 catch에서 에러 무시 → 2초 후 재폴링 → 무한 반복

**추가 영향**

- `UserChannel`은 `key={session.currentSession?.id}`로 마운트되어 있어 세션 전환 시 폴링이 내부적으로 리셋됨
- 하지만 `App.tsx` 레벨의 `currentRunId`는 살아있으므로 새 세션에서도 이전 run의 agentMessages가 덧씌워질 위험 존재

---

### Bug 3 — [Medium] useSession.deleteSession 클로저 캡처 — 비동기 처리 중 세션 전환 발생 시 의도치 않은 세션 강제 전환

**위치**
- `frontend/src/hooks/useSession.ts:41-59`

**문제 코드**

```typescript
const deleteSession = useCallback(async (id: string) => {
  await api.deleteSession(id)          // ← 비동기 대기 A
  const list = await api.getSessions() // ← 비동기 대기 B
  setSessions(list)
  if (currentSession?.id === id) {     // ← 클로저에 캡처된 값 사용!
    if (list.length > 0) {
      const detail = await api.getSession(list[0].id)  // ← 비동기 대기 C
      setCurrentSession(detail)
      setMessages(detail.messages)
    } else {
      ...
    }
  }
}, [currentSession?.id])  // ← 의존성에 id만 있고, 비동기 실행 도중 변경 가능
```

**재현 시나리오**

1. `currentSession = {id: "A"}` — useCallback이 `currentSession?.id = "A"` 를 클로저에 캡처
2. 사용자가 세션 A 삭제 버튼 클릭 → `deleteSession("A")` 실행
3. 비동기 대기 A, B 진행 중 사용자가 세션 B를 클릭해 전환 → `currentSession = {id: "B"}`
4. `currentSession?.id` 변경으로 새 `deleteSession` 함수 생성되지만 **이미 실행 중인 인스턴스는 영향 없음**
5. 대기 완료 후: `if ("A" === "A")` → **true**
6. `list[0]`(임의의 첫 번째 세션)으로 `setCurrentSession(detail)` 호출
7. **사용자가 이미 B로 전환했는데 다른 세션으로 강제 이동됨**

---

### Bug 4 — [Medium] AgentMessage.run_id에 FK가 없어 데이터 정합성이 미보장

**위치**
- `backend/app/models/db.py:76`

**문제 코드**

```python
class AgentMessage(Base):
    __tablename__ = "agent_messages"
    ...
    run_id: Mapped[str] = mapped_column(Text, index=True)  # FK 없음! 단순 Text
```

**비교: Run은 user_messages에 실제 FK 보유**

```python
class Run(Base):
    user_message_id: Mapped[str] = mapped_column(ForeignKey("user_messages.id"))  # ✅ FK 있음
```

**영향**

- `AgentMessage.run_id`는 단순 문자열이므로 DB가 참조 무결성을 보장하지 않음
- Bug 1 시나리오에서: 세션 삭제 후 `flush_callback`이 이미 존재하지 않는 `agent_msg.id`로 `UPDATE`를 실행해도 에러 없이 통과 (FK가 있었다면 Run 존재 여부 검증 가능)
- 향후 코드 변경으로 session_id 없이 AgentMessage가 생성되는 경우 cascade delete 대상에서 누락될 수 있음

---

### Bug 5 — [Low] 삭제 실패 시 UI 오류 처리 없음

**위치**
- `frontend/src/components/SessionList/index.tsx:140-143`
- `frontend/src/hooks/useSession.ts:41-59`

**문제 코드**

```tsx
// SessionList/index.tsx:140-143
onClick={(e) => {
  e.stopPropagation()
  onDeleteSession(sess.id)  // ← 반환된 Promise를 무시
}}
```

```typescript
// useSession.ts:41 — try/catch 없음
const deleteSession = useCallback(async (id: string) => {
  await api.deleteSession(id)  // ← 실패 시 예외 전파
  ...
}, [currentSession?.id])
```

**영향**

- 네트워크 오류 또는 404 응답 시 unhandled promise rejection
- 세션 목록이 갱신되지 않아 UI가 삭제 전 상태로 남음 (유령 세션 표시)

---

## 버그 심각도 요약

| # | 심각도 | 영역 | 핵심 내용 |
|---|--------|------|----------|
| 1 | **Critical** | Backend | 실행 중 세션 삭제 → CLI 미취소 + FK 꺼짐 → 고아 레코드 영구 생성 |
| 2 | **High** | Frontend | 삭제 핸들러에서 currentRunId 미리셋 → 삭제된 Run으로 무한 폴링 |
| 3 | **Medium** | Frontend | deleteSession 클로저 캡처 → 비동기 중 세션 전환 시 엉뚱한 세션으로 강제 이동 |
| 4 | **Medium** | Backend/DB | AgentMessage.run_id FK 없음 → 데이터 정합성 미보장 |
| 5 | **Low** | Frontend | 삭제 API 실패 시 오류 처리 없음 → 유령 세션 UI |

---

---

## 수정 적용 결과

수정 일자: 2026-03-02

### 수정 파일 목록

| 파일 | 수정 내용 | 대응 Bug |
|------|----------|----------|
| `backend/app/models/db.py` | `PRAGMA foreign_keys=ON;` 추가 | Bug 1a |
| `backend/app/models/db.py` | `AgentMessage.run_id` → `ForeignKey("runs.id")` | Bug 4 |
| `backend/app/services/session_service.py` | 삭제 순서 `AgentMessage→Run→UserMessage→Session`으로 변경 | Bug 4 |
| `backend/app/routers/sessions.py` | 삭제 전 활성 Run 감지 + `cancel_current()` 호출 | Bug 1b |
| `backend/app/agents/reader.py` | Solo/Team 완료 후 + 예외 처리에서 run 존재 여부 재확인 후 DB 쓰기 | Bug 1c |
| `backend/migrations/versions/80a5ace788b6_add_fk_agent_message_run_id.py` | Alembic 마이그레이션 (FK 추가) | Bug 4 |
| `frontend/src/App.tsx` | `handleDeleteSession` 핸들러 추가 (`setCurrentRunId(null)`, `setCurrentMode(null)`) | Bug 2 |
| `frontend/src/hooks/useSession.ts` | `currentSessionIdRef`로 클로저 캡처 방지, `try/catch` 추가 | Bug 3, Bug 5 |
| `backend/tests/test_api_sessions.py` | 3개 테스트 추가 (cascade, active run cancel, no cancel) | Bug 1, Bug 4 |
| `backend/tests/test_session_service.py` | 2개 테스트 추가 (children 삭제 확인, false 반환 확인) | Bug 1, Bug 4 |
| `backend/tests/test_team_orchestration.py` | `full_task` 포맷 반영해 assertion 수정 (기존 실패 테스트 수정) | — |

### 테스트 결과

- **백엔드**: 127개 전체 PASSED (`uv run pytest -v`)
- **프론트엔드**: 타입 에러 0개, 린트 에러 0개 (`npx tsc --noEmit && npm run lint`)

---

## 수정 방향 (참고용)

### Bug 1 수정
```python
# session_service.py — delete_session에 CLI 취소 추가
from app.services.cli_service import cancel_current

async def delete_session(db: AsyncSession, session_id: str) -> bool:
    session = await db.get(models.Session, session_id)
    if session is None:
        return False
    await cancel_current()  # ← 추가: 실행 중인 CLI 프로세스 종료
    await db.execute(delete(models.Run).where(...))
    ...
```
```python
# db.py — FK 강제 활성화
cursor.execute("PRAGMA foreign_keys=ON;")  # ← 추가
```

### Bug 2 수정
```tsx
// App.tsx — 삭제 전용 핸들러 추가
const handleDeleteSession = (id: string) => {
  setCurrentRunId(null)   // ← 추가
  setCurrentMode(null)    // ← 추가
  session.deleteSession(id)
}
// ...
onDeleteSession={handleDeleteSession}
```

### Bug 3 수정
```typescript
// useSession.ts — currentSession?.id를 클로저 대신 ref로 관리
const currentSessionIdRef = useRef(currentSession?.id)
useEffect(() => { currentSessionIdRef.current = currentSession?.id }, [currentSession?.id])

const deleteSession = useCallback(async (id: string) => {
  await api.deleteSession(id)
  const list = await api.getSessions()
  setSessions(list)
  if (currentSessionIdRef.current === id) {  // ← ref 사용으로 항상 최신 값
    ...
  }
}, [])  // 의존성 배열 비움
```

### Bug 4 수정
```python
# db.py — AgentMessage.run_id에 FK 추가
run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
```

### Bug 5 수정
```tsx
// SessionList/index.tsx
onClick={(e) => {
  e.stopPropagation()
  void onDeleteSession(sess.id).catch(() => {
    // 오류 토스트 또는 재시도 UI 표시
  })
}}
```
