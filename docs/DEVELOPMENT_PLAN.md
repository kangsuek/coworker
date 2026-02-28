# 상세 개발 계획: Coworker

> **기준 문서**: PRD v1.2.0
> **작성일**: 2026-02-28
> **대상**: Phase 1 (웹 UI MVP)
> **예상 기간**: 6 스프린트 (각 스프린트 3~5일)
> **개발 방법론**: TDD (Test-Driven Development)

---

## 목차

1. [개발 순서 개요](#1-개발-순서-개요)
2. [Sprint 1: 프로젝트 기반 구축](#2-sprint-1-프로젝트-기반-구축)
3. [Sprint 2: CLI 서비스 및 핵심 인프라](#3-sprint-2-cli-서비스-및-핵심-인프라)
4. [Sprint 3: Solo 모드 End-to-End](#4-sprint-3-solo-모드-end-to-end)
5. [Sprint 4: 프론트엔드 기초 및 Solo UI](#5-sprint-4-프론트엔드-기초-및-solo-ui)
6. [Sprint 5: Team 모드 백엔드](#6-sprint-5-team-모드-백엔드)
7. [Sprint 6: Team UI 및 마무리](#7-sprint-6-team-ui-및-마무리)
8. [파일별 구현 명세](#8-파일별-구현-명세)
9. [테스트 전략](#9-테스트-전략)
10. [위험 요소 및 대응](#10-위험-요소-및-대응)

---

## 1. 개발 순서 개요

### 1.1 의존 관계 그래프

```
Sprint 1: 기반 구축
    │
    ▼
Sprint 2: CLI 서비스 + 핵심 인프라
    │
    ▼
Sprint 3: Solo 백엔드
    │
    ▼
Sprint 4: 프론트엔드 기초 및 Solo UI
    │
    ▼
Solo E2E 검증 (마일스톤 1)
    │
    ▼
Sprint 5: Team 백엔드
    │
    ▼
Sprint 6: Team UI + 마무리
    │
    ▼
Phase 1 완료 (마일스톤 2)
```

### 1.2 마일스톤

| 마일스톤 | 시점 | 완료 조건 |
|---------|------|---------|
| **M1: Solo E2E** | Sprint 3~4 완료 | 사용자 메시지 → Reader Solo 응답 → UI 표시 → 세션 저장 |
| **M2: Phase 1 완료** | Sprint 6 완료 | Team 모드 포함 전체 기능 동작, PRD Section 12 성공 기준 충족 |

### 1.3 TDD 개발 규칙

모든 기능 개발은 **TDD(Test-Driven Development)** 사이클을 따른다.

#### 태스크 내 TDD 사이클

1. **🔴 RED**: 실패하는 테스트를 먼저 작성한다. `pytest` 실행 시 FAIL 확인.
2. **🟢 GREEN**: 테스트를 통과하는 **최소한의 코드**를 작성한다. `pytest` 실행 시 PASS 확인.
3. **🔵 REFACTOR**: 테스트가 통과하는 상태를 유지하며 코드를 개선한다.

#### Sprint 간 게이트 규칙

- **다음 Sprint 진입 전, 현재 Sprint까지의 모든 테스트가 100% 통과해야 한다.**
- 게이트 검증 명령: `cd backend && uv run pytest -v` (전체 테스트 스위트)
- 프론트엔드: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
- **1개라도 실패하면 다음 Sprint 진행 금지.**
- 상세 진행 체크리스트는 `docs/TODO.md` 에서 관리한다.

---

## 2. Sprint 1: 프로젝트 기반 구축

> **목표**: 개발 환경 셋업, 프로젝트 스캐폴딩, DB 스키마 생성
> **기간**: 3일
> **PRD 참조**: Section 9 (개발 환경 구성)

### 2.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 1-1 | 프로젝트 루트 구조 생성 | `justfile`, `.env.example`, `.gitignore` | `just setup` 성공 |
| 1-2 | 백엔드 프로젝트 초기화 | `backend/pyproject.toml`, `backend/.env.example` | `cd backend && uv sync` 성공 |
| 1-3 | FastAPI 앱 스켈레톤 | `backend/app/main.py` | `just backend` → `http://localhost:8000/docs` 접속 확인 |
| 1-4 | SQLAlchemy 모델 정의 | `backend/app/models/db.py` | 4개 테이블 모델 정의 완료 |
| 1-5 | Alembic 초기화 + 마이그레이션 | `backend/migrations/`, 초기 마이그레이션 | `just migrate` → DB 파일 생성, 테이블 확인 |
| 1-6 | Pydantic 스키마 정의 | `backend/app/models/schemas.py` | 요청/응답 모델 타입 체크 통과 |
| 1-7 | 프론트엔드 프로젝트 초기화 | `frontend/` (Vite + React + TypeScript + TailwindCSS) | `cd frontend && npm run dev` → `http://localhost:5173` 접속 |
| 1-8 | Claude CLI 설치 확인 스크립트 | `justfile`의 `setup` 태스크 | `just setup` 시 Claude CLI 미설치 경고 |

### 2.2 상세 구현

#### 1-4. SQLAlchemy 모델 (`backend/app/models/db.py`)

PRD ADR-002 DB 스키마를 SQLAlchemy ORM 모델로 변환한다.

```python
# 4개 테이블: sessions, user_messages, agent_messages, runs
# 모든 PK는 UUID (Python uuid4)
# created_at은 server_default=func.now()
# runs.status: queued | running | done | cancelled | error
# agent_messages.status: working | done | error | cancelled
```

핵심 포인트:
- `aiosqlite` 엔진으로 async session 생성
- DB 연결 시 WAL 모드 활성화: `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=5000;`
- `backend/app/models/db.py`에 `async def get_db()` 의존성 함수 정의

#### 1-6. Pydantic 스키마 (`backend/app/models/schemas.py`)

```python
# 요청 모델
class ChatRequest:
    session_id: UUID | None  # 생략 시 새 세션 자동 생성
    message: str

# 응답 모델
class ChatResponse:
    run_id: UUID
    session_id: UUID

class RunStatus:
    status: Literal["queued", "thinking", "solo", "delegating", "working", "integrating", "done", "error", "cancelled"]
    progress: str | None
    response: str | None      # done 상태에서만
    mode: Literal["solo", "team"] | None
    agents: list[AgentInfo] | None

class AgentMessage:
    id: UUID
    sender: str
    role_preset: str
    content: str
    status: Literal["working", "done", "error", "cancelled"]
    created_at: datetime

class AgentMessagesResponse:
    messages: list[AgentMessage]
    has_more: bool

# CLI 분류 결과 (F-001)
class ClassificationResult:
    mode: Literal["solo", "team"]
    reason: str
    agents: list[AgentPlan]
    user_status_message: str | None

class AgentPlan:
    role: Literal["Researcher", "Coder", "Reviewer", "Writer", "Planner"]
    task: str
```

### 2.3 완료 조건

- [ ] `just setup` → 백엔드·프론트엔드 의존성 설치 + Claude CLI 확인
- [ ] `just backend` → FastAPI Swagger UI 접속
- [ ] `just frontend` → Vite 개발 서버 접속
- [ ] `just migrate` → SQLite DB 생성, 4개 테이블 존재 확인
- [ ] `ruff check .` → 린트 에러 없음

---

## 3. Sprint 2: CLI 서비스 및 핵심 인프라

> **목표**: Claude CLI 래퍼, Global Execution Lock, 세션 서비스 구현
> **기간**: 4일
> **PRD 참조**: ADR-004, ADR-006, F-001a~F-001c

### 3.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 2-1 | CLI 서비스 구현 (Popen + 라인 스트리밍) | `backend/app/services/cli_service.py` | 단위 테스트: CLI 호출 → stdout 라인 콜백 |
| 2-2 | Global Execution Lock 구현 | `cli_service.py` 내 Lock 래퍼 | 동시 2개 호출 시 순차 실행 확인 |
| 2-3 | JSON 파싱 폴백 체인 구현 | `backend/app/services/classification.py` | 정상 JSON / 비정상 JSON / 완전 실패 3가지 케이스 테스트 |
| 2-4 | 세션 CRUD 서비스 | `backend/app/services/session_service.py` | 생성·조회·목록 단위 테스트 |
| 2-5 | 설정 관리 (pydantic-settings) | `backend/app/config.py` | `.env` 로드 확인 |

### 3.2 상세 구현

#### 2-1. CLI 서비스 (`backend/app/services/cli_service.py`)

PRD ADR-004 코드 패턴을 그대로 적용한다.

```
핵심 함수:
├── _call_claude_sync()      # 동기: Popen + stdout 라인 루프
├── call_claude_streaming()  # 비동기: asyncio.to_thread() 래퍼
├── _cli_lock                # asyncio.Lock (Global Execution Lock)
└── LineBufferFlusher        # 0.5초 간격 배치 DB 쓰기 (threading.Timer)
    ├── _lock                # threading.Lock (버퍼 스왑 시 동시성 보호)
    ├── append(line)         # on_line 콜백에서 호출 (Lock 획득 → 인메모리 추가)
    ├── flush()              # Lock 획득 → 버퍼 스왑 → 스왑된 데이터를 DB에 UPDATE
    └── stop()               # Agent 완료 시 잔여 버퍼 flush + 타이머 정지
```

구현 포인트:
- `on_line` 콜백은 동기 함수 (스레드에서 실행되므로)
- **`on_line`은 인메모리 버퍼에만 추가하고, 별도 flush 스레드가 0.5초 간격으로 DB에 배치 기록한다** (배치 쓰기). LLM 출력이 빠르게 다수 라인을 생성하므로, 라인별 DB UPDATE는 Lock 경합 및 I/O 지연을 유발한다. 프론트엔드 폴링 간격(2초)에 비해 0.5초 flush는 충분한 실시간성을 제공한다
- **`LineBufferFlusher`의 스레드 안전성**: `append()`(Popen stdout 루프 = 생산자)와 `flush()`(Timer 스레드 = 소비자)가 동일 버퍼에 동시 접근하므로, `threading.Lock`으로 보호한 **버퍼 스왑(Swap) 패턴**을 사용한다. `flush()` 시 Lock 획득 → 기존 버퍼를 로컬 변수로 교체 → 빈 리스트로 초기화 → Lock 해제 → 로컬 데이터를 DB에 기록. 이 방식은 Lock 보유 시간을 최소화하여 `append()` 블로킹을 방지한다
- DB 배치 기록은 동기 `sqlite3`로 별도 connection 사용 (aiosqlite가 아닌)
- `CLAUDE_CLI_PATH`, `CLAUDE_CLI_TIMEOUT` 환경변수에서 읽기
- **`subprocess.Popen(..., start_new_session=True)`로 새 프로세스 그룹 생성** → 취소 시 `os.killpg()`로 Claude CLI와 모든 자식 프로세스를 일괄 종료하여 고아(Orphan) 프로세스 방지. 현재 실행 중인 `proc` 객체를 인스턴스에 보관 (상세: Sprint 5 취소 기능)

#### 2-2. Global Execution Lock

```python
# cli_service.py
_cli_lock = asyncio.Lock()
_current_proc: subprocess.Popen | None = None

async def execute_with_lock(coro):
    """Lock 획득 후 실행. 대기 중이면 queued 상태."""
    async with _cli_lock:
        return await coro

async def cancel_current():
    """현재 실행 중인 CLI 프로세스 + 자식 프로세스 전체 종료."""
    if _current_proc and _current_proc.poll() is None:
        import os, signal
        try:
            # 프로세스 그룹 전체 종료 (고아 프로세스 방지)
            os.killpg(os.getpgid(_current_proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
```

#### 2-3. JSON 파싱 폴백 체인 (`backend/app/services/classification.py`)

```
parse_classification(raw_output: str) -> ClassificationResult:
    │
    ├── 1단계: json.loads(raw_output) → Pydantic 검증 (F-001a)
    │   └── 성공 → return
    │
    ├── 2단계: 정규식으로 { ... } 추출 → 재파싱 (F-001b)
    │   └── re.search(r'\{[\s\S]*\}', raw_output)
    │   └── 성공 → return
    │
    └── 3단계: Solo 폴백 (F-001c)
        └── return ClassificationResult(mode="solo", reason="파싱 실패", ...)
```

테스트 케이스:
1. 정상 JSON → Pydantic 검증 통과
2. `"Here is the result: {...}"` → 정규식 추출 성공
3. `"I cannot classify this"` → Solo 폴백
4. 필수 필드 누락 JSON → Pydantic 실패 → 정규식 시도

### 3.3 완료 조건

- [ ] `pytest tests/test_cli_service.py` → CLI mock 테스트 통과
- [ ] `pytest tests/test_classification.py` → 4가지 폴백 시나리오 통과
- [ ] Global Lock: 2개 동시 호출 시 첫 번째 완료 후 두 번째 실행 확인
- [ ] LineBufferFlusher: 다수 스레드에서 동시 append + flush 시 데이터 누락 없음 확인
- [ ] 세션 CRUD: 생성 → 목록 → 상세 조회 테스트 통과

---

## 4. Sprint 3: Solo 모드 End-to-End

> **목표**: 사용자 메시지 → Reader Solo 응답 → DB 저장의 전체 흐름 동작
> **기간**: 4일
> **PRD 참조**: F-001~F-002, F-005, ADR-005

### 4.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 3-1 | Reader Agent 구현 (분류 + Solo 응답) | `backend/app/agents/reader.py` | 분류 → Solo → 응답 생성 단위 테스트 |
| 3-2 | `POST /api/chat` 엔드포인트 | `backend/app/routers/chat.py` | `curl` → run_id 반환, 백그라운드 처리 시작 |
| 3-3 | `GET /api/runs/{run_id}` 엔드포인트 | `backend/app/routers/chat.py` | 상태 변화: queued → thinking → solo → done |
| 3-4 | 세션 엔드포인트 (목록·상세·생성) | `backend/app/routers/sessions.py` | CRUD API 테스트 |
| 3-5 | 백그라운드 실행 관리 (BackgroundTasks) | `reader.py` + `chat.py` | POST 즉시 반환, GET으로 상태 추적 |
| 3-6 | 통합 테스트: Solo E2E | `tests/test_solo_e2e.py` | POST → 폴링 → done + response 확인 |

### 4.2 상세 구현

#### 3-1. Reader Agent (`backend/app/agents/reader.py`)

```python
class ReaderAgent:
    async def process_message(self, session_id, user_message, run_id):
        """전체 처리 흐름 (백그라운드에서 실행)"""
        # 1. runs 상태 → "thinking"
        # 2. 분류 CLI 호출 (--output-format json)
        # 3. parse_classification() 으로 결과 파싱
        # 4-A. Solo → runs 상태 "solo" → 응답 CLI 호출 → runs 상태 "done"
        # 4-B. Team → (Sprint 5에서 구현)

    async def _classify(self, user_message) -> ClassificationResult:
        """복잡도 분류 시스템 프롬프트 + CLI 호출"""

    async def _solo_respond(self, user_message) -> str:
        """Solo 모드 응답 생성"""
```

분류 시스템 프롬프트 (핵심):
```
당신은 사용자 요청의 복잡도를 판단하는 분류기입니다.
반드시 아래 JSON 형식으로만 응답하세요.

Solo 기준: 단일 도메인, 단일 결과물, 사실 조회, 간단한 코드
Team 기준: 복수 도메인, 리서치+코드+문서 조합, 복수 전문 영역

{
  "mode": "solo" | "team",
  "reason": "판단 근거",
  "agents": [],  // solo면 빈 배열
  "user_status_message": null | "메시지"
}
```

#### 3-2~3-3. REST 엔드포인트 (`backend/app/routers/chat.py`)

```
POST /api/chat
  요청: { "session_id": "...", "message": "..." }
  처리:
    1. session_id 없으면 새 세션 생성
    2. user_message 레코드 저장
    3. run 레코드 생성 (status: "queued")
    4. BackgroundTasks에 reader.process_message() 등록
    5. 즉시 반환: { "run_id": "...", "session_id": "..." }

GET /api/runs/{run_id}
  응답:
    {
      "status": "thinking" | "solo" | "done" | ...,
      "progress": "...",
      "response": "...",   // done에서만
      "mode": "solo",
      "agents": null
    }
```

#### 3-5. 백그라운드 실행

FastAPI의 `BackgroundTasks`는 단순하지만 충분하다. Reader의 `process_message()`가 백그라운드에서 실행되면서 `runs` 테이블의 `status`를 업데이트하고, 프론트엔드는 2초 폴링으로 상태를 추적한다.

```
POST /api/chat  →  run 생성 (queued)  →  즉시 반환
                         │
                    BackgroundTask
                         │
                    Lock 획득 대기 (queued → running)
                         │
                    분류 CLI (thinking)
                         │
                    Solo 응답 CLI (solo)
                         │
                    응답 저장 (done)
```

### 4.3 완료 조건

- [ ] `POST /api/chat` → `run_id` 즉시 반환 (< 100ms)
- [ ] `GET /api/runs/{run_id}` 폴링 → 상태 변화 추적 가능
- [ ] Solo 모드: 사용자 메시지 → 15초 이내 최종 응답
- [ ] `GET /api/sessions/{session_id}` → 대화 히스토리 반환
- [ ] JSON 파싱 폴백: 비정상 CLI 출력에서도 Solo 응답 성공

---

## 5. Sprint 4: 프론트엔드 기초 및 Solo UI

> **목표**: React 앱 구조, User Channel UI, 폴링 훅, Solo 모드 완전 동작
> **기간**: 5일
> **PRD 참조**: Section 10 (UI/UX 명세), F-020~F-023

### 5.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 4-1 | API 타입 및 클라이언트 | `frontend/src/types/api.ts`, `frontend/src/lib/api.ts` | 타입 체크 통과 |
| 4-2 | `useRunPolling` 훅 | `frontend/src/hooks/useRunPolling.ts` | 2초 간격 폴링, done에서 정지 |
| 4-3 | `useSession` 훅 | `frontend/src/hooks/useSession.ts` | 세션 생성·전환·히스토리 로드 |
| 4-4 | 레이아웃 (2패널) | `frontend/src/App.tsx` | User Channel / Agent Channel 분할 |
| 4-5 | User Channel 컴포넌트 | `frontend/src/components/UserChannel/` | 메시지 표시, 입력, 전송 |
| 4-6 | StatusBadge 컴포넌트 | `frontend/src/components/UserChannel/StatusBadge.tsx` | 7개 상태 표시 |
| 4-7 | 마크다운 렌더링 | MessageBubble 내 마크다운 | 코드 블록 하이라이팅 포함 |
| 4-8 | 세션 사이드바 | `frontend/src/components/SessionList/` | 세션 목록·전환·새 세션 |
| 4-9 | Agent Channel 대기 상태 | `frontend/src/components/AgentChannel/index.tsx` | Solo 시 "대기 중" 표시 |

### 5.2 상세 구현

#### 4-1. API 클라이언트 (`frontend/src/lib/api.ts`)

```typescript
const API_BASE = '/api';

export const api = {
  chat: (req: ChatRequest) => post<ChatResponse>("/chat", req),
  getRunStatus: (runId: string) => get<RunStatus>(`/runs/${runId}`),
  getAgentMessages: (runId: string) => get<AgentMessagesResponse>(`/runs/${runId}/agent-messages`),
  cancelRun: (runId: string) => post(`/runs/${runId}/cancel`),
  getSessions: () => get<Session[]>("/sessions"),
  createSession: () => post<Session>("/sessions"),
  getSession: (id: string) => get<SessionDetail>(`/sessions/${id}`),
};
```

#### 4-2. useRunPolling 훅

```
useRunPolling(runId: string | null)
  ├── 2초 + 지터(±300ms) 간격 GET /api/runs/{run_id}
  │   └── interval = 2000 + Math.random() * 600 - 300
  ├── status가 "done" | "error" | "cancelled" → 폴링 정지
  ├── 반환: { status, progress, response, mode, agents }
  └── cleanup: 컴포넌트 언마운트 시 폴링 정지
```

> **지터(Jitter) 적용 근거**: `useRunPolling`과 `useAgentPolling`이 동일한 2초 간격을 사용하면, 동시에(또는 거의 같은 시점에) 2개의 API 요청이 발사되어 SQLite 읽기/쓰기 경합을 유발할 수 있다. 각 훅에 ±300ms 지터를 적용하여 요청 시점을 분산시킨다.

#### 4-5. User Channel 컴포넌트 구조

```
UserChannel/
├── index.tsx           # 메시지 목록 + 입력 영역
├── MessageBubble.tsx   # 개별 메시지 (user/reader 분기)
└── StatusBadge.tsx     # Reader 상태 표시 (7개 상태)
```

메시지 흐름:
1. 사용자 메시지 전송 → API 호출 → `runId` 수신
2. `useRunPolling(runId)` 시작
3. StatusBadge에 현재 상태 표시 (thinking → solo → done)
4. `done` 시 response를 새 MessageBubble로 추가

#### 4-7. 마크다운 렌더링

의존성: `react-markdown` + `rehype-highlight` (또는 `react-syntax-highlighter`)

```
MessageBubble (role === "reader")
└── <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
      {content}
    </ReactMarkdown>
```

### 5.3 완료 조건 (마일스톤 M1)

- [ ] 메시지 입력 → 전송 → StatusBadge 상태 변화 → Reader 응답 표시
- [ ] 응답에 마크다운·코드 블록이 올바르게 렌더링됨
- [ ] Agent Channel에 "대기 중" 표시 (Solo 모드)
- [ ] 세션 사이드바: 목록 표시, 세션 전환, 새 세션 생성
- [ ] 브라우저 새로고침 후 이전 대화 히스토리 복원
- [ ] Vite proxy 설정 → `localhost:5173` → `localhost:8000` API 프록시

---

## 6. Sprint 5: Team 모드 백엔드

> **목표**: Sub-Agent 프리셋, Context Assembler, Team 오케스트레이션 전체 구현
> **기간**: 5일
> **PRD 참조**: F-003~F-004, F-010~F-014, ADR-001, ADR-006

### 6.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 5-1 | Sub-Agent 기반 클래스 | `backend/app/agents/sub_agent.py` | 시스템 프롬프트 + CLI 호출 단위 테스트 |
| 5-2 | 5개 프리셋 시스템 프롬프트 | `backend/app/agents/presets/*.py` | 각 프리셋별 응답 품질 수동 검증 |
| 5-3 | Context Assembler 구현 | `backend/app/agents/reader.py` 내 | 이전 결과 주입된 프롬프트 생성 테스트 |
| 5-4 | Team 오케스트레이션 루프 | `backend/app/agents/reader.py` 내 | 순차 실행 + 결과 통합 테스트 |
| 5-5 | Agent Channel DB 기록 | `session_service.py` 확장 | Popen 라인 → agent_messages 기록 확인 |
| 5-6 | `GET /api/runs/{run_id}/agent-messages` | `backend/app/routers/chat.py` 확장 | 중간 출력 폴링 테스트 |
| 5-7 | 취소 기능 구현 | `POST /api/runs/{run_id}/cancel` | Solo·Team 취소 테스트 |
| 5-8 | 통합 테스트: Team E2E | `tests/test_team_e2e.py` | 분류 → 순차 실행 → 통합 → done |

### 6.2 상세 구현

#### 5-1. Sub-Agent 기반 클래스 (`backend/app/agents/sub_agent.py`)

```python
class SubAgent:
    def __init__(self, name: str, role_preset: str, system_prompt: str):
        self.name = name
        self.role_preset = role_preset
        self.system_prompt = system_prompt

    async def execute(self, task: str, context: str | None, on_line: callable) -> str:
        """CLI 호출로 태스크 수행. context는 이전 Agent 결과."""
        prompt = self._build_prompt(task, context)
        return await call_claude_streaming(
            system_prompt=self.system_prompt,
            user_message=prompt,
            on_line=on_line,
        )

    def _build_prompt(self, task: str, context: str | None) -> str:
        if context:
            return f"--- 이전 작업 결과 (참고용) ---\n{context}\n--- 끝 ---\n\n{task}"
        return task
```

#### 5-2. 프리셋 시스템 프롬프트

| 프리셋 | 시스템 프롬프트 핵심 |
|--------|----------------|
| Researcher | "당신은 리서치 전문가입니다. 사실에 기반하여 조사하고, 출처를 명시하며, 구조화된 보고서를 작성합니다." |
| Coder | "당신은 시니어 소프트웨어 엔지니어입니다. 클린 코드를 작성하고, 에러 처리를 포함하며, 코드에 대한 설명을 제공합니다." |
| Reviewer | "당신은 코드/문서 리뷰어입니다. 논리적 오류, 개선점, 베스트 프랙티스 위반을 지적하고 대안을 제시합니다." |
| Writer | "당신은 테크니컬 라이터입니다. 주어진 자료를 바탕으로 명확하고 읽기 쉬운 문서를 작성합니다." |
| Planner | "당신은 프로젝트 플래너입니다. 복잡한 작업을 단계별로 분해하고, 각 단계의 담당자와 산출물을 정의합니다." |

#### 5-3~5-4. Context Assembler + Team 오케스트레이션

```python
# reader.py
async def _team_execute(self, classification, user_message, run_id):
    """Team 모드 전체 흐름"""
    # 1. runs 상태 → "delegating"
    # 2. Agent Channel에 팀 구성 메시지 기록
    results = {}

    for i, agent_plan in enumerate(classification.agents):
        # 3. runs 상태 → "working" + progress 갱신
        agent = self._create_agent(agent_plan)

        # 4. Context Assembler: 이전 결과 조립
        context = self._assemble_context(results)

        # 5. LineBufferFlusher로 배치 DB 쓰기 (스레드 안전)
        flusher = LineBufferFlusher(agent_msg_id, flush_interval=0.5)
        flusher.start()
        def on_line(line):
            flusher.append(line)  # Lock 획득 → 인메모리 버퍼 추가만

        # 6. Agent 실행
        result = await agent.execute(agent_plan.task, context, on_line)
        flusher.stop()  # 잔여 버퍼 flush + 타이머 정지
        results[agent.name] = result

        # 7. agent_messages status → "done"

    # 8. runs 상태 → "integrating"
    # 9. 통합 CLI 호출
    final = await self._integrate_results(user_message, results)

    # 10. user_messages에 최종 응답 저장
    # 11. runs 상태 → "done"
```

Context Assembler 세부 로직 (PRD ADR-006 준수):
```python
CONTEXT_CHAR_LIMIT = 3000  # 개별 Agent 결과의 임계치

async def _assemble_context(self, results: dict[str, str]) -> str | None:
    if not results:
        return None

    parts = []
    for agent_name, result in results.items():
        if len(result) > CONTEXT_CHAR_LIMIT:
            # PRD ADR-006: 컨텍스트 초과 시 별도 CLI 호출로 요약
            result = await self._summarize_for_context(agent_name, result)
        parts.append(f"[{agent_name} 결과]:\n{result}")

    return "\n\n".join(parts)

async def _summarize_for_context(self, agent_name: str, content: str) -> str:
    """긴 결과물을 다음 Agent에 전달할 수 있도록 CLI 호출로 요약."""
    return await call_claude_streaming(
        system_prompt="이전 Agent의 작업 결과를 다음 Agent가 참고할 수 있도록 핵심 내용만 간결하게 요약하세요. "
                      "코드가 포함된 경우 핵심 로직과 주요 함수 시그니처를 보존하세요.",
        user_message=f"다음은 {agent_name}의 작업 결과입니다. 요약해주세요:\n\n{content}",
        on_line=lambda _: None,  # 요약은 중간 출력 불필요
    )
```

> **주의**: 요약 CLI 호출은 추가 비용(시간)이 발생한다. 비용 표시(PRD 비기능 요구사항)에서 실시간으로 호출 수를 갱신해야 한다. 단순 Truncation은 코드 결과에서 중간이 잘려 다음 Agent가 치명적 문맥 상실을 겪을 수 있으므로, PRD 명세대로 요약 호출을 사용한다.

#### 5-7. 취소 기능

```
POST /api/runs/{run_id}/cancel
  1. runs.status가 "queued" | "running" | "thinking" | "solo" | "working" | "integrating"이 아니면 무시
  2. cli_service.cancel_current() → os.killpg()로 프로세스 그룹 전체 종료
     - Claude CLI(Node.js)는 내부적으로 자식 프로세스를 스폰하므로,
       process.terminate() (SIGTERM)만으로는 부모만 종료되고 자식이 고아로 남음
     - Popen 생성 시 start_new_session=True → 프로세스 그룹 할당
     - os.killpg(pgid, SIGTERM) → 부모 + 모든 자식 프로세스 일괄 종료
  3. Team 모드: 남은 순차 실행 중단 플래그 설정
  4. runs.status → "cancelled"
  5. 완료된 Sub-Agent 결과는 agent_messages에 보존
```

### 6.3 완료 조건

- [ ] Team 분류 → 2~3개 Sub-Agent 순차 실행 → 결과 통합 → 최종 응답
- [ ] Agent Channel: 각 Agent의 중간 출력이 DB에 기록됨
- [ ] `GET /api/runs/{run_id}/agent-messages` → 실행 중 중간 출력 반환
- [ ] Context Assembler: 2번째 Agent의 프롬프트에 1번째 결과 포함 확인
- [ ] 취소: Team 실행 중 취소 → 부분 결과 보존 + "cancelled" 상태

---

## 7. Sprint 6: Team UI 및 마무리

> **목표**: Agent Channel UI, 취소 버튼, 내보내기, 에러 처리, 전체 통합 검증
> **기간**: 5일
> **PRD 참조**: F-024, F-030~F-035, Section 12 성공 기준

### 7.1 태스크 목록

| # | 태스크 | 산출물 | 검증 |
|---|-------|-------|------|
| 6-1 | `useAgentPolling` 훅 | `frontend/src/hooks/useAgentPolling.ts` | Agent Channel 메시지 폴링 |
| 6-2 | Agent Channel 메시지 목록 | `frontend/src/components/AgentChannel/` | 발신자·배지·타임스탬프 표시 |
| 6-3 | Agent Channel 중간 출력 표시 | AgentMessage 컴포넌트 | working 상태 → 라인 누적 표시 |
| 6-4 | Team 상태 표시 (User Channel) | StatusBadge 확장 | delegating → working(N/M) → integrating → done |
| 6-5 | 취소 버튼 구현 | User Channel 입력 영역 | Solo·Team 취소 동작 확인 |
| 6-6 | Agent Channel 요약 표시 | AgentStatusBar 컴포넌트 | "3 Agents · 소요 시간: 8분" |
| 6-7 | Agent Channel 내보내기 | 내보내기 버튼 | 텍스트/JSON 다운로드 |
| 6-8 | 에러 처리 UI | 에러 메시지 컴포넌트 | CLI 실패·타임아웃 시 사용자 메시지 |
| 6-9 | 전체 통합 테스트 | 수동 + 자동 테스트 | PRD Section 12 성공 기준 충족 |

### 7.2 상세 구현

#### 6-1. useAgentPolling 훅

```typescript
function useAgentPolling(runId: string | null, mode: "solo" | "team" | null, isVisible: boolean) {
  // mode가 "team"이 아니면 폴링하지 않음
  // isVisible이 false (Agent Channel 탭이 비활성)이면 폴링 일시 중지
  // 2초 + 지터(±300ms) 간격 GET /api/runs/{run_id}/agent-messages
  // has_more가 false이고 run이 done → 폴링 중단
  // 반환: { messages: AgentMessage[], isPolling: boolean }
}
```

> **조건부 폴링**: Agent Channel이 화면에 보이지 않을 때(`isVisible=false`)는 폴링을 일시 중지하여 불필요한 네트워크 요청과 DB 접근을 방지한다. 탭 전환 시 즉시 1회 fetch 후 정상 폴링을 재개한다.

#### 6-2~6-3. Agent Channel 컴포넌트

```
AgentChannel/
├── index.tsx          # 메시지 목록 + 상태바 + 내보내기
├── AgentMessage.tsx   # 개별 Agent 메시지
│   ├── 헤더: 🔵 Researcher-A [Researcher] 09:14
│   ├── 본문: content (working 시 타이핑 애니메이션)
│   └── 상태: ✅ 완료 / ⏳ 작업 중 / ❌ 오류
└── AgentStatusBar.tsx # 팀 요약 (Agent 수, 소요 시간, 상태)
```

`working` 상태의 메시지는 폴링마다 content가 증가한다. 이전 content와 비교하여 새로운 부분만 하이라이팅하거나, 자동 스크롤을 적용한다.

#### 6-5. 취소 버튼

```
입력 영역:
├── 대기/실행 중 → [취소 ✕] 버튼 표시 (전송 버튼 대체)
├── 클릭 → POST /api/runs/{run_id}/cancel
├── 응답 수신 → StatusBadge "cancelled" 표시
└── Team: "N개 중 M개 완료 후 취소됨" 메시지 표시
```

### 7.3 완료 조건 (마일스톤 M2)

- [ ] **분류 정확도**: 테스트 케이스 20개 중 18개 이상 정확
- [ ] **Solo 응답**: 15초 이내
- [ ] **Team 진행 표시**: 폴링 2초 이내에 상태 업데이트
- [ ] **Agent Channel**: 모든 Sub-Agent 결과 누락 없이 표시
- [ ] **세션 복원**: 새로고침 후 이전 대화 완전 복원
- [ ] **취소**: Solo/Team 모두 정상 동작
- [ ] **에러 처리**: CLI 실패 시 사용자에게 명확한 메시지

---

## 8. 파일별 구현 명세

### 8.1 백엔드 파일 목록

| 파일 | Sprint | 주요 역할 | PRD 참조 |
|------|--------|---------|---------|
| `app/main.py` | 1 | FastAPI 앱, CORS, 라우터 등록, 시작 이벤트(WAL 설정) | Section 9 |
| `app/config.py` | 2 | pydantic-settings 기반 환경변수 관리 | Section 9.3 |
| `app/models/db.py` | 1 | SQLAlchemy 모델 4개 테이블, async engine, WAL 설정 | ADR-002 |
| `app/models/schemas.py` | 1 | Pydantic 요청/응답/분류 결과 모델 | F-001, ADR-005 |
| `app/routers/chat.py` | 3, 5 | `/api/chat`, `/api/runs/*` 엔드포인트 | ADR-005 |
| `app/routers/sessions.py` | 3 | `/api/sessions/*` 엔드포인트 | F-040~F-042 |
| `app/services/cli_service.py` | 2 | Popen 래퍼, asyncio.to_thread, Global Lock, 취소 | ADR-004 |
| `app/services/classification.py` | 2 | JSON 파싱 + 3단계 폴백 체인 | F-001a~F-001c |
| `app/services/session_service.py` | 2, 5 | 세션·메시지·run CRUD | ADR-002 |
| `app/agents/reader.py` | 3, 5 | Reader Agent: 분류, Solo, Team, Context Assembler | F-001~F-006, ADR-006 |
| `app/agents/sub_agent.py` | 5 | Sub-Agent 기반 클래스 | F-010~F-014 |
| `app/agents/presets/__init__.py` | 5 | presets 패키지 초기화 | ADR-001 |
| `app/agents/presets/researcher.py` | 5 | Researcher 시스템 프롬프트 | ADR-001 |
| `app/agents/presets/coder.py` | 5 | Coder 시스템 프롬프트 | ADR-001 |
| `app/agents/presets/reviewer.py` | 5 | Reviewer 시스템 프롬프트 | ADR-001 |
| `app/agents/presets/writer.py` | 5 | Writer 시스템 프롬프트 | ADR-001 |
| `app/agents/presets/planner.py` | 5 | Planner 시스템 프롬프트 | ADR-001 |

### 8.2 프론트엔드 파일 목록

| 파일 | Sprint | 주요 역할 | PRD 참조 |
|------|--------|---------|---------|
| `src/App.tsx` | 4 | 2패널 레이아웃, 세션 상태 관리 | Section 10.1 |
| `src/lib/api.ts` | 4 | API 클라이언트 (7개 엔드포인트) | ADR-005 |
| `src/types/api.ts` | 4 | TypeScript 타입 정의 | Pydantic 스키마 대응 |
| `src/hooks/useRunPolling.ts` | 4 | 실행 상태 폴링 (2초+지터) | F-005 |
| `src/hooks/useAgentPolling.ts` | 6 | Agent Channel 메시지 폴링 (2초+지터, 조건부) | F-030 |
| `src/hooks/useSession.ts` | 4 | 세션 생성·전환·히스토리 | F-040~F-042 |
| `src/components/UserChannel/index.tsx` | 4 | 메시지 목록 + 입력 + 전송/취소 | F-020, F-024 |
| `src/components/UserChannel/MessageBubble.tsx` | 4 | 마크다운 렌더링, 역할별 스타일 | F-021 |
| `src/components/UserChannel/StatusBadge.tsx` | 4, 6 | 7개 상태 표시 | Section 10.2 |
| `src/components/AgentChannel/index.tsx` | 4, 6 | Agent 메시지 목록 + 대기 상태 | F-030, F-033 |
| `src/components/AgentChannel/AgentMessage.tsx` | 6 | Agent 메시지 (배지, 타임스탬프, 중간 출력) | F-031 |
| `src/components/AgentChannel/AgentStatusBar.tsx` | 6 | 팀 요약 (Agent 수, 시간, 상태) | F-034 |
| `src/components/SessionList/index.tsx` | 4 | 세션 목록 사이드바 | F-040 |

### 8.3 테스트 파일 목록

| 파일 | Sprint | 테스트 대상 |
|------|--------|-----------|
| `tests/conftest.py` | 2 | CLI mock fixture, 인메모리 DB fixture |
| `tests/test_cli_service.py` | 2 | CLI 호출 mock, 타임아웃, Lock |
| `tests/test_classification.py` | 2 | JSON 파싱 3단계 폴백 |
| `tests/test_session_service.py` | 2 | 세션 CRUD |
| `tests/test_reader.py` | 3 | Reader Agent 분류, Solo 응답, 에러 처리 |
| `tests/test_api_chat.py` | 3 | POST /api/chat, GET /api/runs, agent-messages |
| `tests/test_api_sessions.py` | 3 | 세션 API 엔드포인트 CRUD |
| `tests/test_background.py` | 3 | BackgroundTasks + Lock 연동 |
| `tests/test_solo_e2e.py` | 3 | Solo 모드 전체 흐름 |
| `tests/test_sub_agent.py` | 5 | SubAgent 클래스 실행, 프롬프트 빌드 |
| `tests/test_presets.py` | 5 | 5개 프리셋 시스템 프롬프트 존재 검증 |
| `tests/test_context_assembler.py` | 5 | 프롬프트 체이닝 검증 |
| `tests/test_team_orchestration.py` | 5 | Team 오케스트레이션 상태 흐름 |
| `tests/test_cancel.py` | 5 | Solo·Team 취소 |
| `tests/test_team_e2e.py` | 5 | Team 모드 전체 흐름 |

---

## 9. 테스트 전략

### 9.1 테스트 계층

```
┌─────────────────────────────────────┐
│         E2E (수동 테스트)              │  ← Sprint 6: 브라우저에서 전체 흐름
├─────────────────────────────────────┤
│       통합 테스트 (httpx)             │  ← Sprint 3, 5: API 엔드포인트
├─────────────────────────────────────┤
│       단위 테스트 (pytest)            │  ← Sprint 2: 서비스 레이어
└─────────────────────────────────────┘
```

### 9.2 CLI Mock 전략

실제 Claude CLI 없이 테스트하기 위해 `cli_service.py`의 CLI 호출을 mock한다.

```python
# conftest.py
@pytest.fixture
def mock_claude_cli(monkeypatch):
    async def fake_call(system_prompt, user_message, on_line, **kwargs):
        if kwargs.get("output_json"):
            return '{"mode": "solo", "reason": "test", "agents": [], "user_status_message": null}'
        return "Mock response for: " + user_message
    monkeypatch.setattr("app.services.cli_service.call_claude_streaming", fake_call)
```

### 9.3 테스트 케이스: Solo/Team 분류 (20개)

| # | 입력 | 기대 분류 | 기대 Agent |
|---|------|---------|-----------|
| 1 | "Python에서 리스트 정렬하는 방법" | Solo | - |
| 2 | "LangGraph 최신 버전이 뭐야?" | Solo | - |
| 3 | "이 함수의 버그 고쳐줘: def add(a,b): return a-b" | Solo | - |
| 4 | "Hello" | Solo | - |
| 5 | "FastAPI에서 CORS 설정하는 법" | Solo | - |
| 6 | "JSON 파싱 에러 해결 방법" | Solo | - |
| 7 | "현재 시간 알려줘" | Solo | - |
| 8 | "Docker Compose 예제 보여줘" | Solo | - |
| 9 | "경쟁사 3개 제품 비교 분석 후 보고서 작성" | Team | Researcher, Writer |
| 10 | "코드 구현 + 테스트 작성 + 문서화" | Team | Coder, Reviewer, Writer |
| 11 | "기술 조사 후 구현하고 블로그로 정리" | Team | Researcher, Coder, Writer |
| 12 | "FastAPI 성능 분석 + 개선 코드 + 블로그" | Team | Coder, Researcher, Writer |
| 13 | "이 코드 리뷰하고 개선 버전 작성해줘" | Team | Reviewer, Coder |
| 14 | "프로젝트 계획을 세우고 각 단계별 코드 작성" | Team | Planner, Coder |
| 15 | "보안 취약점 조사 + 패치 코드 + 보고서" | Team | Researcher, Coder, Writer |
| 16 | "REST API 설계하고 구현하고 문서 작성" | Team | Planner, Coder, Writer |
| 17 | "3개 DB 벤치마크 후 최적 선택 근거 문서화" | Team | Researcher, Writer |
| 18 | "이 PR 코드 리뷰하고 승인 의견 작성" | Team | Reviewer, Writer |
| 19 | "CI/CD 파이프라인 설계 + 스크립트 작성" | Team | Planner, Coder |
| 20 | "마이크로서비스 전환 계획 수립 후 1단계 구현" | Team | Planner, Coder |

---

## 10. 위험 요소 및 대응

| # | 위험 | 영향도 | 대응 |
|---|------|:-----:|------|
| R1 | Claude CLI 응답 지연 (120초 초과) | 높음 | 타임아웃 자동 종료 + 사용자 알림. 환경변수로 타임아웃 조정 가능 |
| R2 | CLI JSON 출력 불안정 (hallucination) | 높음 | F-001a~c 3단계 폴백 체인으로 100% 처리. Solo 폴백이 최종 안전망 |
| R3 | Popen stdout 버퍼링으로 실시간성 저하 | 중간 | `bufsize=1` (라인 버퍼링) 설정. `PYTHONUNBUFFERED=1` 환경변수 |
| R4 | 동시 요청 시 Lock 대기 시간 증가 | 중간 | 프론트엔드에서 `queued` 상태 표시. 단일 사용자 macOS 앱이므로 빈도 낮음 |
| R5 | Context Assembler 컨텍스트 크기 초과 | 중간 | 3000자 임계치 초과 시 별도 CLI 호출로 요약 후 주입 (PRD ADR-006). 요약 호출로 인한 추가 지연(~10초)은 비용 표시에서 실시간 반영 |
| R6 | aiosqlite와 동기 sqlite3 혼용 시 DB 충돌 | 중간 | WAL 모드 + busy_timeout으로 완화. on_line은 0.5초 배치 쓰기로 DB 접근 빈도 대폭 감소. 별도 connection 사용 |
| R7 | Claude CLI 구독 요금제 변경/제한 | 낮음 | .env에서 CLI 경로 변경 가능. SDK 전환은 cli_service.py 인터페이스만 교체 |

---

*이 문서는 PRD v1.2.0을 기반으로 작성되었으며, 개발 진행에 따라 업데이트됩니다.*
