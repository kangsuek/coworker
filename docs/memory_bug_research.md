# 전역 메모리 기능 버그 조사 보고서

조사일: 2026-03-08
조사 범위: 전역 메모리 저장·조회·주입 전 흐름 (백엔드 + 프론트엔드)

---

## 전체 흐름 요약

```
[사용자 입력] → chat API → create_run (queued)
  → BackgroundTask: process_message()
      ├─ "(기억)" startswith → 직접 저장
      ├─ "(기억)" in message → LLM 생성 후 저장
      └─ 일반 메시지 → 분류 → Solo/Team
  → update_run_status("done") → SSE broadcast
  → 프론트엔드 onDone → addMessage()
  → 사이드바 메모리 패널 (useMemory 훅)
```

---

## 발견된 버그 목록

---

### BUG-01 [심각도: HIGH] 채팅 트리거로 메모리 저장 후 사이드바 미갱신

**위치**: `frontend/src/App.tsx` → `onDone` 콜백 / `frontend/src/hooks/useMemory.ts`

**증상**:
`(기억) 내용` 또는 `대화를 요약하여 (기억)에 저장해줘`로 메모리를 저장하면, 채팅창에는 "✅ 기억했습니다"가 표시되지만 **사이드바 전역 메모리 패널은 즉시 갱신되지 않는다**. 페이지를 새로고침해야 새 항목이 보인다.

**원인**:
`useMemory` 훅은 마운트 시 1회만 `api.getMemories()`를 호출한다.

```typescript
// useMemory.ts
useEffect(() => {
    api.getMemories().then(setMemories).catch(() => {})
}, [])  // ← 마운트 1회만 실행
```

`App.tsx`의 `onDone` 콜백은 `memories` 상태를 갱신하는 로직이 없다. 백엔드에서 DB에 저장했지만 프론트엔드 상태는 stale 상태로 유지된다.

**재현**:
1. 채팅에 `(기억) 테스트 항목` 입력
2. "✅ 기억했습니다" 응답 확인
3. 사이드바 "전역 메모리" 패널 → 새 항목 없음

**수정 방향**:
`useMemory`에 `refreshMemories()` 함수를 추가하고, `App.tsx`의 `onDone`에서 응답이 "✅ 기억했습니다"로 시작하면 호출한다.

```typescript
// App.tsx onDone 내부
if (response.startsWith('✅ 기억했습니다')) {
    refreshMemories()
}
```

---

### BUG-02 [심각도: MEDIUM] 메모리 처리 중 Run 상태가 "queued"에서 바로 "done"으로 점프

**위치**: `backend/app/agents/reader.py` → `process_message()`

**증상**:
`(기억)` 트리거(직접 저장·LLM 생성 모두)가 감지된 경우, Run 상태가 `queued → thinking → done` 순서를 거치지 않고 `queued → done`으로 직접 전환된다. 프론트엔드 상태 표시기가 "대기 중"을 표시하다 갑자기 완료된다.

**원인**:
`update_run_status("thinking")` 호출이 메모리 트리거 처리 블록 **이후**에 위치한다.

```python
# reader.py (현재 순서)
_MEMORY_TRIGGER = "(기억)"
if _MEMORY_TRIGGER in user_message:      # ← 메모리 처리 (thinking 상태 없음)
    ...
    content = await self.llm_provider.stream_generate(...)  # LLM 호출
    await create_memory(...)
    await update_run_status("done")       # queued → done (직접 점프)
    return

# 이 코드는 메모리 분기에서 절대 실행되지 않음
await update_run_status("thinking", ...)  # ← 여기까지 도달 불가
```

`thinking_started_at`, `cli_started_at` 타이밍 정보도 누락된다.

**수정 방향**:
메모리 트리거 처리 진입 직전에 `update_run_status("thinking")` 호출 추가.

---

### BUG-03 [심각도: MEDIUM] "(기억)에 저장해줘" 형태의 메시지가 잘못 처리됨

**위치**: `backend/app/agents/reader.py` → `process_message()` 135행

**증상**:
메시지가 "(기억)"으로 시작하지만 뒤에 명령어가 붙는 경우 (예: `(기억)에 저장해줘`, `(기억)해줘, 오늘 회의 내용`), `startswith` 분기가 True가 되어 **뒤따르는 텍스트를 그대로 메모리로 저장**한다.

```python
# 입력: "(기억)에 저장해줘"
content = user_message[len("(기억)"):].strip()
# → content = "에 저장해줘"  ← 이 문자열이 메모리로 저장됨!
```

**사례별 동작**:

| 입력 | 의도 | 실제 동작 |
|------|------|-----------|
| `(기억) 내 이름은 홍길동` | 직접 저장 | ✅ "내 이름은 홍길동" 저장 |
| `(기억)에 저장해줘` | LLM 처리 기대 | ❌ "에 저장해줘" 저장 |
| `(기억)해줘, 오늘 결정사항` | LLM 처리 기대 | ❌ "해줘, 오늘 결정사항" 저장 |
| `대화를 요약해서 (기억)에 저장해줘` | LLM 처리 | ✅ LLM이 처리 (정상) |

**원인**:
`startswith("(기억)")` 조건이 너무 광범위하다. 직접 저장 패턴은 `(기억) ` (공백 포함) 이후에 실제 내용이 오는 경우로 한정해야 한다.

**수정 방향**:
직접 저장 분기의 조건을 강화한다.

```python
# 직접 저장: "(기억) " + 내용 (공백 필수, 뒤에 실질적 내용 있어야 함)
direct_content = user_message[len(_MEMORY_TRIGGER):].lstrip()
is_direct = user_message.startswith(_MEMORY_TRIGGER) and (
    user_message[len(_MEMORY_TRIGGER):len(_MEMORY_TRIGGER)+1] in (' ', '\t', '\n')
)
if is_direct:
    content = direct_content
else:
    # LLM 처리 경로
    ...
```

---

### BUG-04 [심각도: MEDIUM] LLM이 빈 문자열을 반환하면 빈 메모리 항목 저장

**위치**: `backend/app/agents/reader.py` + `backend/app/services/session_service.py`

**증상**:
LLM이 빈 응답을 반환하거나 strip() 후 빈 문자열인 경우, 빈 내용의 메모리 항목이 DB에 저장된다.

**원인**:
`create_memory` 서비스 함수에 빈 문자열 검증이 없다.

```python
# session_service.py
async def create_memory(db: AsyncSession, content: str) -> models.GlobalMemory:
    mem = models.GlobalMemory(content=content.strip())  # 빈 문자열도 허용
    db.add(mem)
    await db.commit()
    ...
```

REST API 라우터는 검증하지만, 내부 호출 경로(reader.py)는 라우터를 거치지 않는다.

```python
# memory.py (라우터) — 검증 있음
if not body.content.strip():
    raise HTTPException(status_code=400, ...)

# reader.py → create_memory() 직접 호출 — 검증 없음
content = await self.llm_provider.stream_generate(...)
content = content.strip()
mem = await create_memory(self.db, content)  # content가 ""일 수 있음
```

**수정 방향**:
`create_memory` 서비스 함수에 유효성 검증 추가, 또는 `reader.py`에서 저장 전 확인.

```python
if not content:
    reply = "⚠️ 메모리 생성에 실패했습니다. (LLM이 빈 응답 반환)"
    ...
    return
```

---

### BUG-05 [심각도: MEDIUM] LLM 메모리 생성 중 SSE 피드백 없음

**위치**: `backend/app/agents/reader.py` 158행

**증상**:
`대화를 요약하여 (기억)에 저장해줘` 같은 자연어 요청 시, LLM이 응답을 생성하는 동안 프론트엔드에 아무런 진행 상태가 표시되지 않는다. 상태 표시기는 "queued" (BUG-02)를 표시하며, `solo_content` 이벤트가 발생하지 않아 스트리밍 텍스트도 없다.

**원인**:
`stream_generate` 호출 시 `on_line` 콜백이 None이다.

```python
content = await self.llm_provider.stream_generate(
    _MEMORY_GEN_PROMPT, prompt,
    model=model_to_use,
    run_id=run_id
    # on_line 없음 → SSE 스트리밍 없음
)
```

또한 BUG-02에 의해 `thinking` 상태 업데이트도 없다.

**수정 방향**:
메모리 생성 중에는 스트리밍 내용을 굳이 노출하지 않는 것이 나을 수 있다(중간 결과가 최종 저장 내용과 다를 수 있으므로). 단, BUG-02(상태 업데이트)는 별도로 수정 필요.

---

### BUG-06 [심각도: LOW] create_memory가 db_lock 없이 호출됨

**위치**: `backend/app/agents/reader.py` 163행

**증상**:
`process_message` 내 모든 DB 쓰기는 `async with self.db_lock:` 블록 내에서 수행되지만, `create_memory()` 만 예외적으로 락 없이 호출된다.

```python
# reader.py
mem = await create_memory(self.db, content)  # ← db_lock 없음
reply = f"✅ 기억했습니다.\n\n> {mem.content}"
async with self.db_lock:                     # 이후 DB 쓰기는 락 있음
    await create_user_message(...)
    await update_run_status(...)
```

현재 각 request가 독립된 DB 세션을 사용하므로 race condition이 발생하지는 않지만, 코드 일관성이 깨진다.

**수정 방향**:
`create_memory` 호출을 `db_lock` 블록 안으로 이동시키거나, 직접 저장·LLM 생성 두 경로 모두 통합 락 블록으로 묶는다.

---

### BUG-07 [심각도: LOW] 팀 모드 메시지에 "(기억)" 포함 시 의도치 않게 메모리 트리거 발생

**위치**: `backend/app/agents/reader.py` 131행

**증상**:
팀 모드 요청 중 "(기억)"이 포함된 메시지는 팀 모드 처리 대신 메모리 트리거로 가로채진다.

**예시**:
```
(팀모드) 1. 과거 프로젝트를 (기억)에 기반하여 분석, 2. 보고서 작성
```
위 메시지는 팀 모드로 처리되길 기대하지만, `"(기억)" in user_message` 조건이 True여서 LLM 메모리 생성 경로로 들어간다.

**원인**:
메모리 트리거 조건이 team_trigger_header 감지보다 먼저 실행되고, 메시지 전체에 대해 `in` 연산을 수행한다.

**수정 방향**:
`team_trigger_header`로 시작하는 메시지는 메모리 트리거 검사를 건너뛰도록 처리 순서 조정 또는 조건 추가.

```python
is_team_trigger = header and user_message.startswith(header)
if not is_team_trigger and _MEMORY_TRIGGER in user_message:
    # 메모리 처리
    ...
```

---

### BUG-08 [심각도: LOW] _MEMORY_TRIGGER가 하드코딩되어 환경변수로 설정 불가

**위치**: `backend/app/agents/reader.py` 130행 / `backend/app/config.py`

**증상**:
`role_add_trigger`는 `settings.role_add_trigger` 환경변수로 설정 가능하지만, 메모리 트리거 `"(기억)"`는 `process_message` 함수 내 지역변수로 하드코딩되어 있다.

```python
# reader.py
_MEMORY_TRIGGER = "(기억)"  # ← 환경변수 미지원

# config.py
role_add_trigger: str = "(역할추가)"  # ← 환경변수 지원
```

**수정 방향**:
`settings.memory_trigger: str = "(기억)"` 를 config.py에 추가하고 reader.py에서 참조.

---

## 우선순위별 수정 계획

| 순위 | 버그 | 심각도 | 수정 공수 |
|------|------|--------|-----------|
| 1 | BUG-01: 사이드바 미갱신 | HIGH | 小 (onDone에서 refresh 호출) |
| 2 | BUG-02: queued→done 직접 점프 | MEDIUM | 小 (thinking 상태 추가) |
| 3 | BUG-03: 잘못된 직접 저장 | MEDIUM | 小 (조건 강화) |
| 4 | BUG-04: 빈 메모리 저장 | MEDIUM | 小 (유효성 검증 추가) |
| 5 | BUG-05: SSE 피드백 없음 | MEDIUM | 中 (BUG-02 선행 필요) |
| 6 | BUG-07: 팀모드 false positive | LOW | 小 (처리 순서 조정) |
| 7 | BUG-06: db_lock 누락 | LOW | 小 (락 블록 이동) |
| 8 | BUG-08: 트리거 하드코딩 | LOW | 小 (config 추가) |
