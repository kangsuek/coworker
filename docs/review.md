# 문서 검토 보고서

> **작성일**: 2026-02-28
> **검토 대상**: PRD.md, DEVELOPMENT_PLAN.md, TODO.md, CLAUDE.md
> **상태**: 수정 대기

---

## 검토 결과 요약

| 우선순위 | 건수 | 설명 |
|:-------:|:---:|------|
| 🔴 심각 | 3 | 개발 시 오작동 또는 구현 불일치 유발 |
| 🟡 보통 | 4 | 문서 간 불일치로 혼란 유발 가능 |
| 🟢 경미 | 3 | 개선 권고 사항 |

---

## 🔴 심각 — 개발 전 반드시 수정

### [S-1] PRD F-024a — 취소 방식이 아키텍처 규칙과 모순

**위치**: `docs/PRD.md` — 4.3 User Channel, F-024a

**문제**: F-024a에서 Solo 취소 방법으로 `process.terminate()`를 명시하고 있으나, 아키텍처 핵심 규칙(CLAUDE.md)에서는 이를 명시적으로 금지한다.

**현재 문구**:
```
F-024a | Solo 취소: 현재 실행 중인 CLI 프로세스를 종료(process.terminate())하고,
         "(취소됨)" 라벨을 대화 히스토리에 기록한다
```

**충돌하는 규칙** (CLAUDE.md 아키텍처 핵심 규칙 #3):
```
프로세스 종료 시 프로세스 그룹 사용
subprocess.Popen(start_new_session=True) + os.killpg(pgid, SIGTERM)
process.terminate() 단독 사용 금지 (Claude CLI의 자식 프로세스가 고아로 남음)
```

ADR-004, DEVELOPMENT_PLAN.md Sprint 5-7 상세 구현도 동일하게 `os.killpg()` 방식을 명시한다.

**수정안**:
```
F-024a | Solo 취소: os.killpg(pgid, SIGTERM)으로 CLI 프로세스 그룹 전체를 종료하고
         (start_new_session=True로 생성된 프로세스 그룹 기준),
         "(취소됨)" 라벨을 대화 히스토리에 기록한다.
```

---

### [S-2] PRD ADR-002 — `runs.status` 값 범위가 실제 구현과 불일치

**위치**: `docs/PRD.md` — 6. 아키텍처 결정, ADR-002 DB 스키마 다이어그램

**문제**: PRD 스키마 다이어그램에 정의된 `runs.status` 값이 실제 구현(`schemas.py`)의 값과 다르다.

| 위치 | 정의된 값 |
|------|---------|
| PRD ADR-002 다이어그램 | `queued \| running \| done \| cancelled \| error` (5개) |
| `schemas.py` `RunStatus.status` | `queued, thinking, solo, delegating, working, integrating, done, error, cancelled` (9개) |
| PRD Section 10.2 상태 표시 표 | `queued, thinking, solo, delegating, working, integrating, done` (7개, error/cancelled 별도) |

`running` 상태는 실제로 사용되지 않으며, 실행 세부 상태(`thinking`, `solo`, `delegating`, `working`, `integrating`)가 DB에 직접 기록된다.

**수정안**: ADR-002 스키마 다이어그램의 `runs.status` 값을 아래와 같이 수정:
```
status (queued | thinking | solo | delegating |
        working | integrating | done | error | cancelled)
```

---

### [S-3] `RunStatus.response` 반환 방법이 DB 스키마에서 불명확

**위치**: `docs/PRD.md` ADR-002, `docs/DEVELOPMENT_PLAN.md` Sprint 3

**문제**: `GET /api/runs/{run_id}` 엔드포인트는 `response: str | None` 필드를 반환하지만, `runs` 테이블에는 `response` 컬럼이 없다. Solo/Team 응답 완료 시 최종 응답 텍스트가 `user_messages` 테이블의 `role="reader"` 레코드에 저장되는데, `run_id`로 이 메시지를 역조회하는 방법이 어디에도 정의되어 있지 않다.

**현재 구조의 문제**:
```
runs 테이블:         response 컬럼 없음
user_messages 테이블: run_id 컬럼 없음 (session_id만 있음)
```

`run_id` → `user_messages.id` 연결 고리가 없어, `GET /api/runs/{run_id}` 구현 시 응답을 어떻게 반환하는지 불명확하다.

**수정안** (두 가지 중 선택):

**옵션 A**: `runs` 테이블에 `response` 컬럼 추가 (단순)
```sql
-- runs 테이블에 response TEXT 컬럼 추가
ALTER TABLE runs ADD COLUMN response TEXT;
```
→ Solo/Team 완료 시 `runs.response`에 최종 응답 저장. `GET /api/runs/{run_id}`에서 직접 조회.

**옵션 B**: `user_messages` 테이블에 `run_id` 컬럼 추가 (정규화)
```sql
-- user_messages 테이블에 run_id TEXT 컬럼 추가
ALTER TABLE user_messages ADD COLUMN run_id TEXT;
```
→ Reader 응답 메시지 저장 시 `run_id`도 함께 기록. JOIN으로 조회.

> **권장**: 옵션 A (runs 테이블에 response 컬럼 추가). 구현이 단순하고, `GET /api/runs/{run_id}` 한 번의 쿼리로 상태와 응답을 함께 반환할 수 있다. Alembic 마이그레이션 1개 추가 필요.

---

## 🟡 보통 — 개발 시작 전 수정 권고

### [M-1] DEVELOPMENT_PLAN.md 의존관계 다이어그램 — Sprint 3→4가 병렬인 것처럼 표시

**위치**: `docs/DEVELOPMENT_PLAN.md` — 1.1 의존관계 그래프

**문제**: 다이어그램이 Sprint 3과 Sprint 4를 병렬 진행 가능한 것처럼 표현하지만, 실제로는 순차 관계이다.

**현재 다이어그램**:
```
Sprint 2: CLI 서비스 + 핵심 인프라
    │
    ├───────────────┐
    ▼               ▼
Sprint 3:        Sprint 4:
Solo 백엔드      프론트엔드 기초   ← 병렬인 것처럼 보임
    │               │
    └───────┬───────┘
```

**충돌하는 규칙** (TODO.md Sprint 4 헤더):
```
진입 조건: Sprint 3 테스트 게이트 100% 통과
```

**수정안**:
```
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

---

### [M-2] DEVELOPMENT_PLAN.md Section 8.3 — 테스트 파일 목록 8개 누락

**위치**: `docs/DEVELOPMENT_PLAN.md` — 8.3 테스트 파일 목록

**문제**: TODO.md에는 15개 테스트 파일이 정의되어 있으나 DEVELOPMENT_PLAN.md에는 7개만 기재되어 있다.

**누락된 파일**:

| 파일 | Sprint | 테스트 대상 |
|------|:------:|-----------|
| `tests/conftest.py` | 2 | CLI mock fixture, 인메모리 DB fixture |
| `tests/test_reader.py` | 3 | Reader Agent 분류, Solo 응답, 에러 처리 |
| `tests/test_api_chat.py` | 3 | POST /api/chat, GET /api/runs, agent-messages |
| `tests/test_api_sessions.py` | 3 | 세션 API 엔드포인트 CRUD |
| `tests/test_background.py` | 3 | BackgroundTasks + Lock 연동 |
| `tests/test_sub_agent.py` | 5 | SubAgent 클래스 실행, 프롬프트 빌드 |
| `tests/test_presets.py` | 5 | 5개 프리셋 시스템 프롬프트 존재 검증 |
| `tests/test_team_orchestration.py` | 5 | Team 오케스트레이션 상태 흐름 |

**수정안**: DEVELOPMENT_PLAN.md Section 8.3 표에 위 8개 파일 추가.

---

### [M-3] PRD Section 9.1 디렉터리 구조 — 2개 파일 누락

**위치**: `docs/PRD.md` — 9.1 디렉터리 구조

**문제**: 실제 구현에 존재하는 파일이 PRD 디렉터리 구조에서 누락되어 있다.

**누락 1**: `frontend/src/hooks/useAgentPolling.ts`

현재 PRD 구조:
```
└── hooks/
    ├── useRunPolling.ts
    └── useSession.ts        ← useAgentPolling.ts 누락
```

수정안:
```
└── hooks/
    ├── useRunPolling.ts     # 실행 상태 폴링 훅
    ├── useAgentPolling.ts   # Agent Channel 메시지 폴링 훅 (Sprint 6)
    └── useSession.ts        # 세션 관리 훅
```

**누락 2**: `backend/app/services/classification.py`

현재 PRD 구조:
```
└── services/
    ├── session_service.py
    └── cli_service.py       ← classification.py 누락
```

수정안:
```
└── services/
    ├── session_service.py   # 세션 CRUD
    ├── cli_service.py       # Claude CLI subprocess 관리
    └── classification.py   # JSON 파싱 3단계 폴백 체인 (F-001a~c)
```

---

### [M-4] F-042 세션 제목 자동 생성 — 구현 방법 및 태스크 미정의

**위치**: `docs/PRD.md` — 4.5 세션 관리, F-042 / `docs/TODO.md`

**문제**: PRD F-042에서 "세션 제목은 첫 번째 사용자 메시지를 기반으로 자동 생성된다"고 명시하지만, 생성 방법과 시점이 정의되어 있지 않고 TODO.md에도 관련 태스크가 없다.

**결정이 필요한 사항**:
- **방법 A**: 첫 메시지를 최대 30자로 truncation (별도 CLI 호출 없음, 즉시 처리)
- **방법 B**: 별도 CLI 호출로 한 줄 제목 생성 (품질은 높지만 추가 시간/비용 발생)

**권장**: 방법 A (truncation). 비용 효율 원칙에 부합하며 구현이 단순하다.

**추가할 내용**:

1. PRD F-042 수정:
```
F-042 | 세션 제목은 첫 번째 사용자 메시지의 앞 30자를 사용하여 자동 생성된다.
         30자 초과 시 "…"을 붙인다. 제목은 session_service의 create_user_message()
         호출 시 세션 title이 null인 경우 함께 업데이트한다.
```

2. TODO.md Sprint 3 태스크 3-4(세션 엔드포인트) 또는 3-5(백그라운드 실행) 하위에 추가:
```
- [ ] 세션 제목 자동 생성: 첫 user 메시지 저장 시 session.title이 null이면
      메시지 앞 30자(초과 시 "…" 추가)로 자동 설정
- [ ] test_session_service.py에 test_auto_title_generation 테스트 추가
```

---

## 🟢 경미 — 개선 권고

### [L-1] DEVELOPMENT_PLAN.md Section 5.2 — API_BASE 예시 코드가 실제 구현과 다름

**위치**: `docs/DEVELOPMENT_PLAN.md` — 5.2 4-1 API 클라이언트

**문제**: 문서 예시가 하드코딩 URL을 사용하지만 실제 구현은 Vite 프록시를 활용하는 상대 경로를 사용한다.

**현재 문서 예시**:
```typescript
const API_BASE = "http://localhost:8000/api";  // 직접 접근 — 오해 유발
```

**실제 `api.ts` 구현**:
```typescript
const API_BASE = '/api';  // Vite 프록시 활용 — 올바른 구현
```

**수정안**: 문서 예시 코드를 실제 구현과 동일하게 수정.

---

### [L-2] PRD ADR-002 DB 스키마 다이어그램 — `agent_messages.run_id` FK 표현 오해 가능

**위치**: `docs/PRD.md` — 6. ADR-002 DB 스키마 다이어그램

**문제**: 다이어그램에서 `agent_messages.run_id`가 `runs` 테이블과 FK 관계처럼 시각적으로 표현되지만, 실제 `db.py`에서는 외래키 제약이 없는 일반 컬럼이다.

**실제 구현** (`db.py`):
```python
run_id: Mapped[str] = mapped_column(Text, index=True)  # FK 제약 없음, 인덱스만 있음
```

**수정안**: 다이어그램 주석에 "(FK 제약 없음, 인덱스 전용)" 표기 추가 또는 다이어그램 연결선 제거.

---

### [L-3] `presets/` 디렉터리 — `__init__.py` 언급 없음

**위치**: `docs/PRD.md` Section 9.1, `docs/DEVELOPMENT_PLAN.md` Section 8.1

**문제**: `backend/app/agents/presets/`를 Python 패키지로 import하려면 `__init__.py`가 필요하다. 디렉터리 구조에 해당 파일이 명시되어 있지 않아, Sprint 5 구현 시 import 오류가 발생할 수 있다.

**수정안**: 디렉터리 구조에 `presets/__init__.py` 추가 명시. TODO.md Sprint 5-2 태스크에 `__init__.py` 생성 항목 추가.

```
└── presets/
    ├── __init__.py      ← 추가
    ├── researcher.py
    ├── coder.py
    ├── reviewer.py
    ├── writer.py
    └── planner.py
```

---

## 수정 우선순위 및 담당 파일

| # | 항목 | 수정 파일 | 우선순위 |
|---|------|---------|:-------:|
| S-1 | F-024a 취소 방식 수정 | PRD.md | 🔴 |
| S-2 | runs.status 값 범위 수정 | PRD.md | 🔴 |
| S-3 | RunStatus.response 반환 방법 결정 및 DB 스키마 반영 | PRD.md + db.py + migrations | 🔴 |
| M-1 | Sprint 3→4 의존관계 다이어그램 수정 | DEVELOPMENT_PLAN.md | 🟡 |
| M-2 | 테스트 파일 목록 8개 추가 | DEVELOPMENT_PLAN.md | 🟡 |
| M-3 | 디렉터리 구조 2개 파일 추가 | PRD.md | 🟡 |
| M-4 | F-042 세션 제목 생성 방법 정의 및 태스크 추가 | PRD.md + TODO.md | 🟡 |
| L-1 | API_BASE 예시 코드 수정 | DEVELOPMENT_PLAN.md | 🟢 |
| L-2 | run_id FK 표현 명확화 | PRD.md | 🟢 |
| L-3 | presets/__init__.py 명시 | PRD.md + DEVELOPMENT_PLAN.md + TODO.md | 🟢 |

---

*이 문서는 개발 착수 전 검토 결과를 기록한 것이며, 수정 완료 후 삭제 또는 archived 상태로 전환한다.*
