# CLAUDE.md — Coworker Project

## 프로젝트 개요

Coworker는 AI Agent 팀 시스템이다. 사용자 요청의 복잡도에 따라 Solo(단독) / Team(다중 Agent) 모드를 자동 전환하는 macOS 데스크톱 앱(Phase 2)의 웹 MVP(Phase 1)를 개발한다.

핵심 구조: `사용자 ↔ Reader Agent(Orchestrator) ↔ Sub-Agents(순차 실행)`

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| AI Engine | Claude CLI (`claude` 명령어, subprocess.Popen) |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), aiosqlite, Alembic |
| Frontend | React (Vite), TypeScript, TailwindCSS v4 |
| DB | SQLite (WAL 모드) |
| 패키지 관리 | uv (Python), npm (JS) |
| 태스크 러너 | just |
| 린트 | ruff (Python), eslint + tsc (TypeScript) |

## 디렉터리 구조

```
coworker/
├── docs/PRD.md                    # 요구사항 + ADR (v1.2.0)
├── docs/DEVELOPMENT_PLAN.md       # 6 Sprint 상세 개발 계획
├── backend/
│   ├── app/main.py                # FastAPI 진입점
│   ├── app/config.py              # pydantic-settings 환경변수
│   ├── app/models/db.py           # SQLAlchemy ORM (4 테이블)
│   ├── app/models/schemas.py      # Pydantic 요청/응답 스키마
│   ├── app/routers/               # chat.py, sessions.py
│   ├── app/services/              # cli_service.py, classification.py, session_service.py
│   ├── app/agents/                # reader.py, sub_agent.py, presets/
│   ├── migrations/                # Alembic
│   └── pyproject.toml             # uv 설정
├── frontend/
│   ├── src/App.tsx                # 2패널 레이아웃
│   ├── src/lib/api.ts             # API 클라이언트
│   ├── src/types/api.ts           # 백엔드 대응 타입
│   ├── src/hooks/                 # useRunPolling, useAgentPolling, useSession
│   └── src/components/            # UserChannel/, AgentChannel/, SessionList/
├── justfile                       # 공통 태스크
└── .env.example                   # 환경변수 템플릿
```

## 빠른 시작

```bash
# 의존성 설치 + Claude CLI 확인
just setup

# DB 마이그레이션
just migrate

# 개발 서버 실행 (백엔드 + 프론트엔드 동시)
just dev

# 개별 실행
just backend    # http://localhost:8000 (FastAPI + Swagger: /docs)
just frontend   # http://localhost:5173 (Vite dev server)
```

## 주요 명령어

```bash
just test       # pytest 실행
just lint       # ruff (backend) + eslint (frontend)
just migrate    # Alembic 마이그레이션 적용
```

백엔드 작업 시:
```bash
cd backend
uv sync                                         # 의존성 설치
uv run ruff check . && uv run ruff format .     # 린트 + 포맷
uv run alembic revision --autogenerate -m "설명"  # 마이그레이션 생성
uv run alembic upgrade head                      # 마이그레이션 적용
uv run pytest -v                                 # 테스트
```

프론트엔드 작업 시:
```bash
cd frontend
npm install          # 의존성 설치
npm run dev          # 개발 서버
npm run build        # 프로덕션 빌드
npx tsc --noEmit     # 타입 체크
npm run lint         # eslint
```

## 코드 스타일

### Python (backend/)
- ruff: line-length=100, target-version="py312"
- 규칙: E, F, I, N, W, UP
- Python 3.12+ 문법 사용 (`str | None`, `list[str]` 등)
- `migrations/versions/`는 린트 제외

### TypeScript (frontend/)
- TailwindCSS 유틸리티 클래스만 사용 (별도 CSS 파일 금지)
- API 호출은 `src/lib/api.ts`의 `api` 객체 사용

## TDD 개발 규칙 (필수)

이 프로젝트는 **TDD(Test-Driven Development)** 를 엄격히 따른다.

### 개발 사이클
1. **🔴 RED**: 실패하는 테스트를 먼저 작성. `pytest` 실행 시 FAIL 확인.
2. **🟢 GREEN**: 테스트를 통과하는 최소한의 코드 작성. `pytest` 실행 시 PASS.
3. **🔵 REFACTOR**: 테스트 통과 상태를 유지하며 코드 개선.

### Sprint 간 게이트
- 다음 Sprint 진입 전, 현재까지의 **모든 테스트가 100% 통과**해야 한다.
- 백엔드: `cd backend && uv run pytest -v` (전체 통과)
- 프론트엔드: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
- **1개라도 실패 시 다음 Sprint 진행 금지.**
- 진행 체크리스트: `docs/TODO.md` 참조

## 아키텍처 핵심 규칙

이 프로젝트를 이해하고 코드를 작성할 때 반드시 지켜야 하는 규칙이다.

### 1. CLI 호출은 asyncio.to_thread()로 감싸기
`subprocess.Popen`은 동기/블로킹이므로 FastAPI 이벤트 루프를 차단한다. 반드시 `asyncio.to_thread()`로 별도 스레드에서 실행한다.

### 2. Global Execution Lock
Claude CLI는 한 번에 1개만 실행한다. `asyncio.Lock`으로 FIFO 대기. 새 요청은 `queued` 상태.

### 3. 프로세스 종료 시 프로세스 그룹 사용
`subprocess.Popen(start_new_session=True)` + `os.killpg(pgid, SIGTERM)`. `process.terminate()` 단독 사용 금지 (Claude CLI의 자식 프로세스가 고아로 남음).

### 4. DB 쓰기는 배치로
CLI stdout 라인별 DB UPDATE 금지. `LineBufferFlusher`로 0.5초 간격 배치 쓰기. `threading.Lock`으로 버퍼 스왑 보호.

### 5. SQLite WAL 모드
모든 DB 연결에서 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;` 설정 필수.

### 6. Context Assembler는 요약 CLI 호출
이전 Agent 결과가 3000자 초과 시 별도 CLI 호출로 요약 후 주입. 단순 truncation 금지.

### 7. 폴링에 지터 적용
`useRunPolling`, `useAgentPolling` 모두 2초 + ±300ms 지터. `useAgentPolling`은 Agent Channel 비활성 시 폴링 중지.

## DB 스키마 (4 테이블)

- **sessions**: 대화 세션 (id, title, created_at, updated_at)
- **user_messages**: User Channel 메시지 (session_id FK, role, content, mode)
- **agent_messages**: Agent Channel 메시지 (session_id FK, run_id, sender, role_preset, content, status)
- **runs**: 실행 기록 (session_id FK, user_message_id FK, mode, status, response, agent_count, started_at, finished_at)

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/chat | 메시지 전송, run_id 즉시 반환 |
| GET | /api/runs/{run_id} | 실행 상태 폴링 |
| GET | /api/runs/{run_id}/agent-messages | Agent 중간 출력 폴링 |
| POST | /api/runs/{run_id}/cancel | 실행 취소 |
| GET | /api/sessions | 세션 목록 |
| POST | /api/sessions | 새 세션 생성 |
| GET | /api/sessions/{session_id} | 세션 상세 (대화 포함) |
| GET | /api/health | 헬스 체크 |

## 환경변수

```
CLAUDE_CLI_PATH=claude          # CLI 실행 경로
CLAUDE_CLI_TIMEOUT=120          # 호출당 타임아웃 (초)
MAX_SUB_AGENTS=5                # Team 모드 최대 Agent 수
DB_PATH=./data/coworker.db     # SQLite 파일 경로
CORS_ORIGINS=http://localhost:5173
```

## 참조 문서

- **PRD**: `docs/PRD.md` — 요구사항, 6개 ADR, 기술 스택, UI/UX 명세
- **개발 계획**: `docs/DEVELOPMENT_PLAN.md` — 6 Sprint 상세, 파일별 명세, 테스트 전략
