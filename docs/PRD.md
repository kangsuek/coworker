# Product Requirements Document: Coworker

> **버전**: 1.2.0
> **작성일**: 2026-02-28
> **상태**: Confirmed
> **대상 독자**: 개발자, AI Agent, LLM 코드 생성 도구

---

## 목차

1. [개요](#1-개요)
2. [핵심 작동 원리](#2-핵심-작동-원리)
3. [대화 채널 명세 및 예시](#3-대화-채널-명세-및-예시)
4. [기능 요구사항](#4-기능-요구사항)
5. [비기능 요구사항](#5-비기능-요구사항)
6. [아키텍처 결정](#6-아키텍처-결정)
7. [기술 스택 및 근거](#7-기술-스택-및-근거)
8. [참고 프레임워크 및 코드베이스](#8-참고-프레임워크-및-코드베이스)
9. [개발 환경 구성](#9-개발-환경-구성)
10. [UI/UX 명세](#10-uiux-명세)
11. [개발 단계](#11-개발-단계)
12. [성공 기준](#12-성공-기준)

---

## 1. 개요

### 1.1 제품 설명

**Coworker**는 사용자의 요청을 분석하여 **단독 처리(Solo)** 또는 **다중 Agent 협업(Team)** 으로 자율적으로 전환하는 AI Agent 팀 시스템이다.

사용자는 **Reader Agent**와 자연어로 대화한다. Reader는 요청의 복잡도를 판단하여:
- 단순한 요청은 혼자 처리한다.
- 복합적인 요청은 전문 Sub-Agent 팀을 구성하여 순차 처리 후 결과를 통합한다.

사용자는 두 개의 분리된 채널을 통해 전체 과정을 관찰할 수 있다:
- **User Channel**: 사용자 ↔ Reader의 주 대화창
- **Agent Channel**: Reader ↔ Sub-Agents의 내부 협업 대화 (읽기 전용)

최종 배포 형태는 **macOS 네이티브 앱**이다.

### 1.2 핵심 가치

| 가치 | 설명 |
|------|------|
| **자율 판단** | 사용자가 복잡도를 신경 쓰지 않아도 Reader가 최적 실행 전략을 선택한다 |
| **투명한 협업** | Agent 간 내부 대화를 사용자에게 공개하여 신뢰성을 높인다 |
| **순차 처리** | 서브 태스크를 전문 Agent가 순차적으로 처리하여 응답 품질을 높인다 |
| **비용 효율** | Claude CLI(구독 기반)를 활용하여 API 토큰 과금 없이 운영한다 |
| **단일 인터페이스** | 복잡한 워크플로우를 단순한 채팅 인터페이스로 추상화한다 |

### 1.3 대표 사용 시나리오

> 사용자: "Python으로 작성된 FastAPI 서버의 성능 병목을 분석하고, 개선 방안 코드와 함께 기술 블로그 초안을 작성해줘"

이 요청은 Reader가 **Team 모드**를 선택한다:
- `Coder` Agent: FastAPI 코드 분석 및 개선 코드 작성
- `Researcher` Agent: 성능 최적화 기법 조사
- `Writer` Agent: 블로그 초안 작성
- Reader: 세 결과를 통합하여 사용자에게 최종 응답 전달

---

## 2. 핵심 작동 원리

### 2.1 Reader Agent의 역할

Reader는 시스템의 **Orchestrator** 이자 사용자의 **유일한 대화 상대**다.

```
사용자 메시지 수신 (REST POST)
      │
      ▼
Reader: 요청 분석 (claude -p --output-format json)
      │
      ├─── Solo 판단 ───► Reader가 직접 응답 생성 (claude -p) ───► 사용자에게 반환
      │
      └─── Team 판단 ───► Sub-Agent 순차 실행 (Context Assembler)
                               │
                               ▼
                          Agent-A (claude -p)  ← 1번
                               │ 결과
                               ▼
                          Reader: Context 조립 (A 결과 → B 프롬프트에 주입)
                               │
                               ▼
                          Agent-B (claude -p)  ← 2번
                               │ 결과
                               ▼
                          Reader: Context 조립 (A+B 결과 → C 프롬프트에 주입)
                               │
                               ▼
                          Agent-C (claude -p)  ← 3번
                               │
                               ▼
                      Reader: 결과 통합 (claude -p)
                               │
                               ▼
                      사용자에게 최종 응답
```

### 2.2 복잡도 분류 메커니즘

Reader의 첫 번째 CLI 호출에서 `--output-format json`으로 분류와 실행 계획을 동시에 반환한다.

```json
// Solo 판단 예시
{
  "mode": "solo",
  "reason": "단순 정보 질의로 단독 처리 가능",
  "agents": [],
  "user_status_message": null
}

// Team 판단 예시
{
  "mode": "team",
  "reason": "코드 분석, 리서치, 문서 작성을 전문 Agent로 순차 처리",
  "agents": [
    {"role": "Coder", "task": "FastAPI 성능 병목 분석 및 개선 코드 작성"},
    {"role": "Researcher", "task": "Python 비동기 성능 최적화 기법 조사"},
    {"role": "Writer", "task": "기술 블로그 초안 작성 (Coder/Researcher 결과 수신 후)"}
  ],
  "user_status_message": "복합 작업을 감지했습니다. 전문 팀과 협업을 시작합니다..."
}
```

### 2.3 Solo vs Team 판단 기준

| 조건 | 판단 | 예시 |
|------|------|------|
| 단일 도메인, 단일 결과물 | Solo | "Python에서 리스트 정렬하는 방법" |
| 사실 조회, 요약 | Solo | "LangGraph의 최신 버전이 뭐야?" |
| 간단한 코드 수정 | Solo | "이 함수의 버그 고쳐줘" |
| 복수 도메인에 걸친 분석 | Team | "경쟁사 3개 제품 비교 분석 후 보고서 작성" |
| 복수 전문 영역에 걸친 서브태스크 | Team | "코드 구현 + 테스트 작성 + 문서화" |
| 리서치 + 코드 + 글쓰기 조합 | Team | "기술 조사 후 구현하고 블로그로 정리" |

---

## 3. 대화 채널 명세 및 예시

### 3.1 채널 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                      Coworker                                   │
├────────────────────────────┬────────────────────────────────────┤
│       USER CHANNEL         │          AGENT CHANNEL             │
│   (사용자 ↔ Reader)          │      (Reader ↔ Sub-Agents)          │
│   [ 양방향 입력 가능 ]         │      [ 읽기 전용 · 관찰 전용 ]          │
└────────────────────────────┴────────────────────────────────────┘
```

---

### 3.2 User Channel 대화 예시

> **시나리오**: 사용자가 멀티 에이전트 프레임워크 리서치를 요청하는 경우 (Team 모드 전환)

---

```
┌─────────────────────────────────────────────────────┐
│  USER CHANNEL                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🤖 Reader  [09:12]                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ 안녕하세요! 무엇을 도와드릴까요?               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│                                   나  [09:13]  👤   │
│   ┌─────────────────────────────────────────────┐  │
│   │ 멀티 에이전트 오케스트레이션을 지원하는 오픈  │  │
│   │ 소스 프레임워크를 조사해줘. GitHub Star 수,  │  │
│   │ 주요 기능, 우리 프로젝트 적합성 포함해서.    │  │
│   └─────────────────────────────────────────────┘  │
│                                                     │
│  🤖 Reader  [09:13]                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ ⚙ 분석 중...                                │   │
│  │                                             │   │
│  │ 복합 리서치 작업을 감지했습니다.              │   │
│  │ 3명의 전문 Agent가 순차적으로 조사합니다.    │   │
│  │                                             │   │
│  │ 👥 팀 구성:                                 │   │
│  │   • Researcher-A: LangGraph 생태계           │   │
│  │   • Researcher-B: CrewAI · Agno · AutoGen   │   │
│  │   • Researcher-C: CopilotKit · AG-UI        │   │
│  │                                             │   │
│  │ ⏳ 진행 중... (1/3 Agent 작업 중)            │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│    ··· ⏳ 진행 중... (2/3 Agent 작업 중) ···        │
│    ··· ⏳ 진행 중... (3/3 Agent 작업 중) ···        │
│    ··· 📝 결과 통합 중... ···                       │
│                                                     │
│  🤖 Reader  [09:21]                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✅ 팀 리서치 완료. 결과를 통합했습니다.       │   │
│  │                                             │   │
│  │ ## 조사 결과 요약                            │   │
│  │                                             │   │
│  │ | 프레임워크   | Stars | 적합도 |            │   │
│  │ |------------|-------|--------|            │   │
│  │ | Agno       | 38k   | ★★★★★ |            │   │
│  │ | CopilotKit | 28k   | ★★★★☆ |            │   │
│  │ | LangGraph  | 25k   | ★★★★☆ |            │   │
│  │ | ...        | ...   | ...    |            │   │
│  │                                             │   │
│  │ **권장 조합**: Agno (백엔드) +               │   │
│  │ AG-UI Protocol (이벤트 표준) +              │   │
│  │ 커스텀 React UI (프론트엔드)                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────┐        │
│  │  메시지를 입력하세요...          [전송 ↵] │        │
│  └─────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

---

### 3.3 Agent Channel 대화 예시

> **동일 시나리오**: Team 작업 진행 중 오른쪽 패널에 순차적으로 표시되는 내부 협업 기록 (실행 중 중간 출력 포함)

---

```
┌─────────────────────────────────────────────────────┐
│  AGENT CHANNEL                     [📋 작업 완료]   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🎯 Reader  [09:13]                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ [팀 구성] 순차 리서치 태스크를 분배합니다.    │   │
│  │                                             │   │
│  │ @Researcher-A: LangGraph, LangSmith,        │   │
│  │   agent-service-toolkit을 조사해줘.         │   │
│  │   C1~C4 기준으로 평가하고 FastAPI 적합성     │   │
│  │   포함해서 보고해.                           │   │
│  │                                             │   │
│  │ @Researcher-B: CrewAI, Agno, AutoGen,       │   │
│  │   AgentScope를 조사해줘. 동일 기준.          │   │
│  │                                             │   │
│  │ @Researcher-C: CopilotKit, AG-UI Protocol,  │   │
│  │   AWS Agent Squad, Mastra를 조사해줘.        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  🔵 Researcher-A  [09:13 → 09:16]  ✅ 완료           │
│  ┌─────────────────────────────────────────────┐   │
│  │ LangGraph: Stars 25.2k, C1:O C2:X C3:부분  │   │
│  │ LangSmith: SaaS Observability, C2:O        │   │
│  │ agent-service-toolkit: Stars 4k,            │   │
│  │   FastAPI 패턴 참고용으로 최적               │   │
│  │                                             │   │
│  │ 권장: LangGraph를 오케스트레이션 엔진으로    │   │
│  │ 채택, LangSmith는 Observability 레이어로    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  🟢 Researcher-B  [09:16 → 09:18]  ✅ 완료           │
│  ┌─────────────────────────────────────────────┐   │
│  │ [완료 보고] → Reader                        │   │
│  │                                             │   │
│  │ Agno: Stars 38k, FastAPI 네이티브,          │   │
│  │   Agent UI (Next.js) 공식 제공. ★★★★★      │   │
│  │ CrewAI: Stars 44.6k, 커뮤니티 최대,         │   │
│  │   UI는 상용 SaaS 중심. ★★★☆☆              │   │
│  │ AG2/AutoGen: ⚠️ maintenance 모드 전환.      │   │
│  │   신규 프로젝트 비추천.                      │   │
│  │ AgentScope: OpenTelemetry 기반 Obs UI       │   │
│  │   우수. FastAPI 직접 상속. ★★★★☆           │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  🟡 Researcher-C  [09:18 → 09:20]  ✅ 완료           │
│  ┌─────────────────────────────────────────────┐   │
│  │ [완료 보고] → Reader                        │   │
│  │                                             │   │
│  │ AG-UI Protocol: Stars 11.5k, FastAPI SSE   │   │
│  │   네이티브 통합, 프로토콜 표준. 채택 권장.   │   │
│  │ CopilotKit: Stars 28k, AG-UI 창시자,        │   │
│  │   React 컴포넌트 + Python SDK 제공.          │   │
│  │ AWS Agent Squad: C1 완전 충족 유일,          │   │
│  │   AnthropicAgent 내장.                      │   │
│  │ Mastra: TypeScript 전용. Python 프로젝트    │   │
│  │   직접 통합 불가.                            │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  🎯 Reader  [09:20 → 09:21]                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ [통합] 3개 보고서를 종합합니다.              │   │
│  │                                             │   │
│  │ 최종 권장 조합 결정:                         │   │
│  │ - Backend: Agno (FastAPI 네이티브)           │   │
│  │ - Frontend: 커스텀 React UI                  │   │
│  │ - 참고: AWS Agent Squad의 C1 패턴           │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ─── 팀 작업 완료 (3 Agents · 소요 시간: 8분 12초) ─│
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 3.4 Solo 모드 예시 (Agent Channel 비활성)

> **시나리오**: 단순 질문 — Agent Channel은 비활성 상태 유지

**User Channel:**
```
사용자: "Python에서 리스트를 역순으로 정렬하는 방법은?"

Reader: list.reverse() 또는 list[::-1] 슬라이싱을 사용합니다.

        # 원본 수정
        my_list = [3, 1, 2]
        my_list.reverse()  # [2, 1, 3]

        # 새 리스트 반환
        reversed_list = my_list[::-1]  # [2, 1, 3]

        sorted()에 reverse=True를 전달하는 방법도 있습니다.
```

**Agent Channel:**
```
[ 대기 중 — Solo 모드에서는 팀 협업이 없습니다 ]
```

---

## 4. 기능 요구사항

### 4.1 Reader Agent 동작

| ID | 요구사항 |
|----|---------|
| F-001 | Reader는 사용자 메시지를 수신하면 첫 번째 CLI 호출(`claude -p --output-format json`)로 Solo/Team 분류와 실행 계획을 동시에 반환한다. JSON 파싱 실패 시 아래 F-001a~F-001c 폴백 전략을 순차 적용한다 |
| F-001a | **1차 폴백 (스키마 검증)**: CLI 출력을 Pydantic 모델로 검증한다. 필수 필드(`mode`, `reason`, `agents`) 누락 시 폴백으로 전환한다 |
| F-001b | **2차 폴백 (JSON 추출)**: 출력이 순수 JSON이 아닌 경우(설명 텍스트 포함 등), 정규 표현식으로 `{ ... }` 블록을 추출하여 재파싱한다 |
| F-001c | **3차 폴백 (Solo 모드)**: 모든 파싱이 실패하면 즉시 Solo 모드로 전환하고, CLI 원본 출력을 Reader의 직접 응답 입력으로 활용한다 |
| F-002 | Solo 판단 시 Reader가 직접 응답을 생성(`claude -p`)하고 완성된 응답을 User Channel에 일괄 표시한다 |
| F-003 | Team 판단 시 필요한 Sub-Agent CLI 호출을 순차적으로 실행하고 태스크를 분배한다. 이전 Agent의 결과를 다음 Agent 프롬프트에 주입하는 Context Assembler(ADR-006)를 적용한다 |
| F-004 | Team 작업 완료 후 Reader가 Sub-Agent 결과들을 통합(`claude -p`)하여 사용자에게 최종 응답을 전달한다 |
| F-005 | Reader는 진행 상태(queued / thinking / solo / delegating / working / integrating / done)를 User Channel에 폴링 기반으로 표시한다. Sub-Agent 실행 중에는 Popen stdout 라인을 DB에 실시간 기록하여 Agent Channel 전용 엔드포인트(`GET /api/runs/{run_id}/agent-messages`) 폴링 시 중간 출력을 반환한다 |
| F-006 | Team 모드 전환 시 User Channel에 구성된 팀 목록, 각 Agent의 역할, 현재 진행 순번(N/M)을 표시한다 |

### 4.2 Sub-Agent 관리

| ID | 요구사항 |
|----|---------|
| F-010 | Sub-Agent는 5개의 역할 프리셋을 가진다: `Researcher`, `Coder`, `Reviewer`, `Writer`, `Planner` |
| F-011 | Reader는 작업 유형에 따라 적합한 프리셋을 동적으로 선택하여 Agent를 생성한다 |
| F-012 | 각 Sub-Agent의 상태(idle / working / done / error / cancelled)를 Agent Channel에서 확인할 수 있다 |
| F-013 | Sub-Agent는 작업 완료 시 결과를 Reader에게 반환하고 종료된다 |
| F-014 | Sub-Agent 오류 시 Reader가 해당 작업을 직접 처리하거나 다른 Agent에게 재위임한다 |

### 4.3 User Channel

| ID | 요구사항 |
|----|---------|
| F-020 | 채팅 입력창, 전송 버튼, 대화 히스토리 뷰를 제공한다 |
| F-021 | Reader의 응답은 마크다운 렌더링을 지원한다 (코드 하이라이팅 포함) |
| F-022 | Reader가 Team 모드로 전환될 때 상태 메시지와 팀 구성 목록을 표시한다 |
| F-023 | 대화 히스토리는 세션 간 SQLite에 저장·복원된다 |
| F-024 | 응답 생성 중 취소 버튼을 제공한다. 취소 동작은 Solo/Team 모드에 따라 아래 F-024a~F-024d를 따른다 |
| F-024a | **Solo 취소**: `os.killpg(pgid, SIGTERM)`으로 CLI 프로세스 그룹 전체를 종료하고(`start_new_session=True`로 생성된 프로세스 그룹 기준), "(취소됨)" 라벨을 대화 히스토리에 기록한다 |
| F-024b | **Team 취소**: 현재 실행 중인 Sub-Agent CLI 프로세스를 종료하고, 남은 순차 실행을 중단한다 |
| F-024c | **부분 결과 처리**: Team 취소 시점에 이미 완료된 Sub-Agent의 결과는 Agent Channel에 보존하고, User Channel에 "N개 중 M개 완료 후 취소됨" 상태를 표시한다 |
| F-024d | **취소 요청 전달**: 프론트엔드는 `POST /api/runs/{run_id}/cancel` 엔드포인트로 취소를 요청하고, 백엔드는 해당 CLI 프로세스에 종료 신호를 전달한다 |

### 4.4 Agent Channel

| ID | 요구사항 |
|----|---------|
| F-030 | User Channel과 분리된 패널에 Agent 간 메시지를 표시한다. Sub-Agent 실행 중에는 Popen stdout 라인 스트리밍으로 DB에 기록된 중간 출력을 폴링하여 실시간에 가깝게 표시하고, 완료 후 최종 결과를 확인할 수 있다 |
| F-031 | 각 메시지에 발신 Agent 이름, 역할 배지, 타임스탬프를 표시한다 |
| F-032 | 사용자는 Agent Channel을 읽기 전용으로만 관찰할 수 있다 |
| F-033 | Solo 모드(Team 작업 없음)일 때는 Agent Channel 패널에 "대기 중" 상태를 표시한다 |
| F-034 | Team 작업 완료(또는 취소) 후 소요 시간, 참여 Agent 수, 완료/취소 상태를 요약으로 표시한다 |
| F-035 | Agent Channel 전체 대화 내용을 텍스트/JSON 형식으로 내보내기할 수 있다 |

### 4.5 세션 관리

| ID | 요구사항 |
|----|---------|
| F-040 | 새 세션 시작, 기존 세션 목록 조회, 세션 전환 기능을 제공한다 |
| F-041 | 각 세션은 User Channel 대화와 Agent Channel 대화를 모두 저장한다 |
| F-042 | 세션 제목은 첫 번째 사용자 메시지의 앞 30자를 사용하여 자동 생성된다. 30자 초과 시 "…"을 붙인다. `session_service`의 `create_user_message()` 호출 시 세션 `title`이 `null`인 경우 함께 업데이트한다 |

---

## 5. 비기능 요구사항

| 범주 | 요구사항 |
|------|---------|
| 성능 | Reader의 Solo/Team 분류 응답은 5초 이내 (CLI 프로세스 시작 + LLM 응답 포함) |
| 성능 | Solo 모드 전체 응답 반환은 15초 이내 |
| 성능 | 프론트엔드 진행 상태 폴링 간격은 2초 |
| 확장성 | Team 모드의 순차 실행 Sub-Agent 수는 환경변수로 제한 (기본값: 5) |
| 신뢰성 | Sub-Agent CLI 호출 오류(exit code ≠ 0) 시 Reader가 폴백 처리하며 사용자에게 상황을 알린다 |
| 신뢰성 | CLI 프로세스가 타임아웃(기본값: 120초) 초과 시 자동 종료하고 에러 처리한다 |
| 보안 | Claude CLI의 인증 정보는 시스템 레벨(`~/.claude/`)에서 관리하며 앱이 직접 취급하지 않는다 |
| 접근성 | 웹 UI는 반응형으로 구현하여 1280px ~ 2560px 화면 지원 |
| 오프라인 | macOS 앱에서 Claude CLI 실행 실패 시 명확한 오류 메시지를 표시한다 |
| 비용 | Claude CLI는 구독 기반(Pro/Max)으로 운영하여 API 토큰 과금을 회피한다 |
| 비용 | Team 모드 전환 시 User Channel에 예상 CLI 호출 수(분류 1회 + Sub-Agent N회 + 통합 1회 = 최소 N+2회)를 표시한다. Context Assembler의 컨텍스트 요약이 필요한 경우 추가 호출이 발생할 수 있으며, 이 경우 실시간으로 호출 수를 갱신한다 |
| 동시성 | Claude CLI는 한 번에 하나의 프로세스만 실행한다 (**Global Execution Lock**). 새 요청이 들어오면 현재 실행이 완료될 때까지 큐에 대기시키고, 사용자에게 대기 상태를 표시한다 |
| 동시성 | Global Execution Lock은 `asyncio.Lock`으로 구현하며, 큐잉된 요청은 FIFO 순서로 처리한다 |
| 보안 | FastAPI 백엔드에 CORS 미들웨어를 설정한다. 개발 환경은 `localhost:5173`(Vite), 프로덕션은 Tauri 앱의 `tauri://localhost`를 허용 origin으로 등록한다 |

---

## 6. 아키텍처 결정

### ADR-001. Sub-Agent 역할 프리셋

**결정: 핵심 5개 고정 프리셋 + Reader가 동적 조합**

| 프리셋 | 역할 | 주요 활용 |
|--------|------|---------|
| `Researcher` | 정보 수집·탐색 | 사실 조회, 비교 분석, 기술 조사 |
| `Coder` | 코드 작성·수정 | 구현, 버그 수정, 리팩토링 |
| `Reviewer` | 검토·비평 | 코드 리뷰, 논리 검증, 팩트체크 |
| `Writer` | 문서·텍스트 작성 | 리포트, 블로그, 이메일 초안 |
| `Planner` | 작업 분해·설계 | 복잡한 요청을 단계와 담당자로 분리 |

Reader는 이 5개를 조합하여 실행 파이프라인을 구성한다.

### ADR-002. 세션 히스토리 저장소

**결정: SQLite + aiosqlite (비동기)**

- FastAPI의 async 환경과 자연스럽게 통합된다
- 세션·메시지·Agent 대화 간 관계를 외래키로 표현한다
- macOS 앱 배포 시 단일 `.db` 파일로 관리된다
- 스키마 변경은 `alembic`으로 관리한다
- **WAL(Write-Ahead Logging) 모드를 활성화한다.** Sub-Agent는 순차 실행되지만, 백엔드가 CLI 결과를 DB에 쓰는 동안 프론트엔드가 2초 간격으로 폴링(읽기)하므로 read/write 동시 접근이 발생한다. WAL 모드가 없으면 `database is locked` 에러가 발생할 수 있다
- DB 연결 시 `PRAGMA journal_mode=WAL;`과 `PRAGMA busy_timeout=5000;`을 설정한다

**DB 스키마:**

```
┌──────────────────┐       ┌──────────────────────────┐
│     sessions     │       │      user_messages       │
├──────────────────┤       ├──────────────────────────┤
│ id (PK, UUID)    │──┐    │ id (PK, UUID)            │
│ title            │  │    │ session_id (FK) ──────────│──┐
│ created_at       │  │    │ role (user|reader)       │  │
│ updated_at       │  │    │ content (TEXT)            │  │
└──────────────────┘  │    │ mode (solo|team)         │  │
                      │    │ created_at               │  │
                      │    └──────────────────────────┘  │
                      │                                   │
                      │    ┌──────────────────────────┐  │
                      │    │     agent_messages       │  │
                      │    ├──────────────────────────┤  │
                      │    │ id (PK, UUID)            │  │
                      ├────│ session_id (FK)          │  │
                      │    │ run_id (TEXT, INDEX)     │  │
                      │    │ sender (TEXT)            │  │
                      │    │ role_preset (TEXT)       │  │
                      │    │ content (TEXT)            │  │
                      │    │ status (working|done|    │  │
                      │    │   error|cancelled)       │  │
                      │    │ created_at               │  │
                      │    └──────────────────────────┘  │
                      │                                   │
                      │    ┌──────────────────────────┐  │
                      │    │        runs              │  │
                      │    ├──────────────────────────┤  │
                      └────│ session_id (FK)          │──┘
                           │ id (PK, UUID)            │
                           │ user_message_id (FK)     │
                           │ mode (solo|team)         │
                           │ status (queued|thinking|  │
                           │   solo|delegating|        │
                           │   working|integrating|    │
                           │   done|error|cancelled)   │
                           │ response (TEXT)          │
                           │ agent_count (INT)        │
                           │ started_at               │
                           │ finished_at              │
                           └──────────────────────────┘
```

| 테이블 | 역할 |
|--------|------|
| `sessions` | 대화 세션 단위. 제목은 첫 사용자 메시지 기반 자동 생성 |
| `user_messages` | User Channel 메시지 (사용자 입력 + Reader 응답). `mode` 필드로 해당 턴의 Solo/Team 여부를 기록 |
| `agent_messages` | Agent Channel 메시지 (Reader ↔ Sub-Agent 내부 대화). `run_id`로 같은 실행 단위를 그룹핑 |
| `runs` | 1회의 사용자 요청에 대한 실행 기록. 최종 응답(), Team 모드의 Agent 수, 소요 시간, 최종 상태를 추적 |

### ADR-003. macOS App Wrapper

**결정: Tauri**

| 항목 | Tauri | Electron |
|------|-------|---------|
| 번들 크기 | ~8 MB | ~150 MB |
| 렌더러 | macOS WKWebView (네이티브) | 번들된 Chromium |
| 메모리 | 낮음 | 높음 |

핵심 로직이 Python 백엔드에 있으므로 Tauri의 Rust 부분은 창 관리·시스템 트레이 등 얇은 래퍼 역할만 담당한다.

### ADR-004. AI 엔진: Claude CLI

**결정: Claude CLI (`claude` 명령어) + subprocess 호출**

Anthropic SDK 대신 Claude CLI를 사용하여 비용을 절감한다.

| 항목 | Claude SDK (API 과금) | Claude CLI (구독 기반) |
|------|---------------------|----------------------|
| 과금 | 입출력 토큰당 과금 | 월 정액 (Pro $20 / Max $100) |
| Team 3-Agent 요청 1회 | 5회 API 호출 비용 발생 | 월정액 내 포함 |
| 호출 방식 | Python `async/await` | `subprocess.Popen` (stdout 라인 스트리밍) |
| Structured Output | JSON Schema 강제 | `--output-format json` + 시스템 프롬프트로 유도 (파싱 실패 시 F-001a~F-001c 폴백) |

**CLI 호출 패턴:**

`subprocess.Popen`으로 stdout을 라인 단위로 읽어 중간 출력을 DB에 실시간 기록한다. 이를 통해 Agent Channel에서 에이전트의 사고 과정을 폴링으로 관찰할 수 있다.

> **주의**: `subprocess.Popen` + stdout 읽기 루프는 동기/블로킹이므로, FastAPI의 async 이벤트 루프를 차단하지 않도록 반드시 `asyncio.to_thread()`로 감싸서 별도 스레드에서 실행한다. 이를 통해 CLI 실행 중에도 폴링·취소 API가 정상 응답할 수 있다.

```python
import subprocess
import asyncio

def _call_claude_sync(
    system_prompt: str,
    user_message: str,
    on_line: callable,
    output_json: bool = False,
    timeout: int = 120,
) -> str:
    cmd = ["claude", "-p", user_message, "--system-prompt", system_prompt]
    if output_json:
        cmd.extend(["--output-format", "json"])

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    lines = []
    try:
        for line in proc.stdout:
            lines.append(line)
            on_line(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {proc.stderr.read()}")
    return "".join(lines)

async def call_claude_streaming(
    system_prompt: str,
    user_message: str,
    on_line: callable,
    output_json: bool = False,
    timeout: int = 120,
) -> str:
    return await asyncio.to_thread(
        _call_claude_sync, system_prompt, user_message, on_line, output_json, timeout
    )
```

**동시성 제어 (Global Execution Lock):**
- Claude CLI는 `~/.claude/` 디렉터리의 세션 상태를 공유하므로 동시에 여러 프로세스를 실행하면 세션 충돌이 발생할 수 있다
- 백엔드에서 `asyncio.Lock`을 사용하여 한 번에 하나의 CLI 프로세스만 실행한다
- Team 모드의 순차 실행(분류 → Sub-Agent N회 → 통합)은 하나의 Lock 획득 내에서 일괄 처리된다
- 새 요청이 Lock 대기 중이면 프론트엔드에 `queued` 상태를 반환하여 사용자에게 대기 상태를 표시한다

**전제 조건:**
- 서버 환경에 Claude CLI가 설치되어 있어야 한다 (`npm install -g @anthropic-ai/claude-code`)
- Claude Pro 또는 Max 구독이 활성화되어 있어야 한다
- CLI 인증은 `~/.claude/` 디렉터리에서 관리되며 앱이 직접 취급하지 않는다

### ADR-005. 통신 프로토콜

**결정: REST API (요청-응답 + 폴링)**

CLI 기반 순차 실행에서는 실시간 토큰 스트리밍이 불가하므로, SSE/WebSocket 대신 **REST API 요청-응답 패턴**을 채택한다.

| 방향 | 프로토콜 | 용도 |
|------|---------|------|
| 클라이언트 → 서버 | **REST POST** | 사용자 메시지 전송, 세션 관리, 취소 요청 |
| 서버 → 클라이언트 | **REST GET (폴링)** | 실행 상태 조회, 완성된 응답 조회 |

**실행 흐름:**

```
1. POST /api/chat          → run_id 반환 (백그라운드 처리 시작)
2. GET  /api/runs/{run_id} → 실행 상태 + User Channel 응답 조회 (polling, 2초 간격)
   → { "status": "queued" }
   → { "status": "working", "progress": "1/3 Agent 작업 중" }
   → { "status": "working", "progress": "결과 통합 중" }
   → { "status": "done", "response": "..." }
3. GET  /api/runs/{run_id}/agent-messages → Agent Channel 중간 출력 조회 (polling, 2초 간격)
   → { "messages": [...], "has_more": true }
   → 실행 중: Popen stdout으로 DB에 기록된 라인들을 실시간 반환
   → 완료 후: 전체 Agent 대화 기록 반환
4. POST /api/runs/{run_id}/cancel → 취소 요청
```

**엔드포인트 요약:**

| 메서드 | 경로 | 용도 |
|--------|------|------|
| `POST` | `/api/chat` | 사용자 메시지 전송, run_id 반환. 요청 바디: `{ "session_id": "UUID", "message": "string" }`. session_id 생략 시 새 세션을 자동 생성한다 |
| `GET` | `/api/runs/{run_id}` | 실행 상태·진행률·최종 응답 조회 |
| `GET` | `/api/runs/{run_id}/agent-messages` | Agent Channel 중간/최종 메시지 조회 |
| `POST` | `/api/runs/{run_id}/cancel` | 실행 취소 요청 |
| `GET` | `/api/sessions` | 세션 목록 조회 |
| `POST` | `/api/sessions` | 새 세션 생성 |
| `GET` | `/api/sessions/{session_id}` | 세션 상세 (히스토리 포함) 조회 |

**폴링 방식을 선택한 근거:**
- CLI subprocess 실행은 비동기 이벤트를 생성하지 않으므로 SSE가 불필요하다
- REST 폴링은 구현이 단순하고 디버깅이 용이하다
- 2초 간격 폴링은 UX상 충분한 반응성을 제공한다
- 프론트엔드/백엔드 모두 추가 프레임워크 의존 없이 구현 가능하다

### ADR-006. Sub-Agent 간 Context Assembler

**결정: Reader가 "프롬프트 체이닝"으로 이전 Agent 결과를 다음 Agent 입력에 주입**

순차 실행에서 이전 Sub-Agent의 결과물이 다음 Sub-Agent에게 전달되지 않으면, 각 Agent가 독립적으로만 작동하여 협업 효과가 없다. Reader의 Context Assembler가 이 문제를 해결한다.

**Context 전달 흐름:**

```
Agent-A 완료 → Reader가 결과 수신
                  │
                  ▼
            Context Assembler
            ┌─────────────────────────────────────┐
            │ 1. 이전 Agent 결과를 요약/정제        │
            │ 2. 다음 Agent의 시스템 프롬프트에 주입 │
            │ 3. 컨텍스트 크기가 임계치 초과 시 축약 │
            └─────────────────────────────────────┘
                  │
                  ▼
            Agent-B 실행 (이전 결과가 포함된 프롬프트)
```

**프롬프트 주입 패턴:**

```
[시스템 프롬프트]
당신은 {role} 전문가입니다.

[이전 Agent 결과 컨텍스트]
--- 이전 작업 결과 (참고용) ---
{Researcher 결과}: {요약된 결과물}
--- 끝 ---

[사용자 태스크]
{해당 Agent에 할당된 태스크}
```

**설계 원칙:**
- Reader만 Context Assembler 역할을 수행한다 (Sub-Agent는 전달받은 프롬프트를 처리할 뿐)
- 이전 결과가 없는 첫 번째 Agent에는 컨텍스트를 주입하지 않는다
- 컨텍스트 크기가 과도할 경우 Reader가 별도 CLI 호출로 요약 후 주입한다

---

## 7. 기술 스택 및 근거

### 7.1 확정된 기술 스택

| 레이어 | 기술 | 선택 근거 |
|--------|------|---------|
| AI Engine | **Claude CLI** (`claude` 명령어) | 구독 기반 비용 절감, subprocess 호출로 단순한 통합 (ADR-004) |
| 오케스트레이션 | **자체 구현** (Python subprocess) | 프레임워크 의존 없이 CLI 순차 호출로 오케스트레이션 |
| 통신 프로토콜 | **REST API** (요청-응답 + 폴링) | 스트리밍 불필요, 구현 단순 (ADR-005) |
| Backend | Python 3.12+, FastAPI | |
| Frontend | React (Vite), TailwindCSS, TypeScript | |
| 세션 저장 | SQLite + aiosqlite + alembic | 단일 파일, async FastAPI 통합 |
| macOS 앱 | Tauri | 8MB 번들, macOS WKWebView 네이티브 |
| 패키지 관리 | uv (Python), npm (JS) | |
| 태스크 러너 | just | |
| 환경 설정 | python-dotenv | |

### 7.2 Claude CLI 설정

| 항목 | 값 | 설명 |
|------|------|------|
| CLI 명령어 | `claude` | `@anthropic-ai/claude-code` npm 패키지 |
| 필수 구독 | Claude Pro ($20/월) 또는 Max ($100/월) | CLI 사용을 위한 구독 필요 |
| 모델 선택 | CLI가 자동 선택 | 구독 플랜에 따라 사용 가능한 최적 모델이 자동 적용 |
| 타임아웃 | 120초 (환경변수로 변경 가능) | Sub-Agent 1회 호출의 최대 실행 시간 |

---

## 8. 참고 프레임워크 및 코드베이스

### 8.1 프레임워크 전체 비교 (2026년 2월 기준)

> 아래 조사는 Claude Code Agent Teams를 활용한 3-Agent 병렬 리서치로 수집되었다.

| 프레임워크 | Stars | C1 복잡도 판단 | C2 Obs UI | C3 분리 채널 | C4 Claude | FastAPI 적합 |
|---|---|---|---|---|---|---|
| **Agno** | 38k | 부분 | 부분 | 부분 | O | **매우 높음** ★ |
| **AG-UI Protocol** | 11.5k | X (프로토콜) | 부분 | 부분 | O | **매우 높음** ★ |
| **LangGraph** | 25.2k | O | X | 부분 | O | 높음 |
| LangSmith | SaaS | X | O | 부분 | O | 높음 |
| agent-service-toolkit | 4k | 부분 | 부분 | X | O | **매우 높음** |
| CrewAI | 44.6k | 부분 | O | X | O | 중간 |
| AgentScope | 15.1k | 부분 | O | 부분 | O | 높음 |
| CopilotKit | 28k | 부분 | O | 부분 | O | 높음 |
| **AWS Agent Squad** | 5k | **O** | X | X | **O (내장)** | 높음 |
| AG2/AutoGen | 54.7k* | 부분 | 부분 | X | O | 중간 ⚠️ |
| Mastra | 19k | 부분 | 부분 | X | O | 낮음 (TS 전용) |

> *microsoft/autogen Stars는 레거시 포함 수치. ag2ai/ag2 포크는 4.2k.

**C1~C4 기준 설명:**
- **C1**: Orchestrator가 요청 복잡도 판단 후 단독/다중 Agent 자동 전환
- **C2**: Agent 간 대화 실시간 Observability UI
- **C3**: 사용자↔Orchestrator / Orchestrator↔Sub-Agent 분리 채널 뷰
- **C4**: Claude API / Anthropic SDK 지원

### 8.2 핵심 발견 사항 및 아키텍처 결정 배경

> 아래 조사를 거쳐, 비용 효율과 개발 단순성을 최우선으로 **Claude CLI + 자체 오케스트레이션** 방식을 채택했다. SDK 기반 프레임워크(Agno, AG-UI 등)는 참고 수준으로 활용한다.

1. **C3 (분리 채널 뷰)를 네이티브로 완전 지원하는 프레임워크는 없다.** 어떤 방식이든 커스텀 구현이 필요하므로, 프레임워크 의존 없이 자체 구현하는 것이 유리하다.

2. **C1 (자동 복잡도 판단)은 CLI의 JSON 출력으로 구현 가능하다.** `claude -p --output-format json`으로 분류 결과를 받아 자체 오케스트레이션에 활용한다.

3. **비용 구조가 핵심 차별점이다.** SDK 기반은 호출당 토큰 과금이 발생하지만, CLI 기반은 월 정액 구독으로 운영하여 Team 모드의 다중 호출 비용을 고정한다.

### 8.3 직접 참고할 코드베이스

| 저장소 | 참고 목적 | URL |
|--------|---------|-----|
| `agno-agi/agent-ui` | Agent 채팅 UI 컴포넌트 디자인 참고 | https://github.com/agno-agi/agent-ui |
| `Eng-Elias/CrewAI-Visualizer` | FastAPI + 에이전트 대화 시각화 UI 패턴 | https://github.com/Eng-Elias/CrewAI-Visualizer |
| `awslabs/agent-squad` | C1 인텐트 분류 패턴 참고 | https://github.com/awslabs/agent-squad |
| `JoshuaC215/agent-service-toolkit` | FastAPI 풀스택 서비스 아키텍처 참고 | https://github.com/JoshuaC215/agent-service-toolkit |

---

## 9. 개발 환경 구성

### 9.1 디렉터리 구조

```
coworker/
├── docs/
│   └── PRD.md
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 진입점
│   │   ├── agents/
│   │   │   ├── reader.py            # Reader Agent (Orchestrator)
│   │   │   ├── sub_agent.py         # Sub-Agent 기반 클래스
│   │   │   └── presets/
│   │   │       ├── __init__.py      # 패키지 초기화
│   │   │       ├── researcher.py    # Researcher 프리셋
│   │   │       ├── coder.py         # Coder 프리셋
│   │   │       ├── reviewer.py      # Reviewer 프리셋
│   │   │       ├── writer.py        # Writer 프리셋
│   │   │       └── planner.py       # Planner 프리셋
│   │   ├── routers/
│   │   │   ├── chat.py              # 채팅 엔드포인트 (REST API)
│   │   │   └── sessions.py          # 세션 관리 엔드포인트
│   │   ├── models/
│   │   │   ├── schemas.py           # Pydantic 모델 (요청/응답)
│   │   │   └── db.py                # SQLite 모델 (SQLAlchemy)
│   │   └── services/
│   │       ├── session_service.py   # 세션 CRUD
│   │       ├── cli_service.py       # Claude CLI subprocess 관리
│   │       └── classification.py   # JSON 파싱 3단계 폴백 체인 (F-001a~c)
│   ├── migrations/                  # alembic 마이그레이션
│   ├── pyproject.toml               # uv 패키지 설정
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── UserChannel/
│   │   │   │   ├── index.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── StatusBadge.tsx
│   │   │   └── AgentChannel/
│   │   │       ├── index.tsx
│   │   │       ├── AgentMessage.tsx
│   │   │       └── AgentStatusBar.tsx
│   │   ├── hooks/
│   │   │   ├── useRunPolling.ts     # 실행 상태 폴링 훅
│   │   │   ├── useAgentPolling.ts   # Agent Channel 메시지 폴링 훅 (Sprint 6)
│   │   │   └── useSession.ts        # 세션 관리 훅
│   │   └── types/
│   │       └── api.ts               # API 요청/응답 타입
│   ├── package.json
│   └── vite.config.ts
├── tauri/                           # macOS App Wrapper (Phase 2)
│   └── src-tauri/                   # Tauri는 frontend/ 빌드 결과를 임베딩한다
│       ├── tauri.conf.json          #   → build.distDir: "../../frontend/dist"
│       └── src/
│           └── main.rs
├── justfile                         # 공통 태스크 정의
└── .env.example
```

### 9.2 justfile

```makefile
# 개발 서버 실행 (백엔드 + 프론트엔드 동시)
dev:
    just backend & just frontend

# 백엔드 개발 서버
backend:
    cd backend && uv run uvicorn app.main:app --reload --port 8000

# 프론트엔드 개발 서버
frontend:
    cd frontend && npm run dev

# 의존성 설치 + Claude CLI 확인
setup:
    @which claude || (echo "Error: Claude CLI not found. Run: npm install -g @anthropic-ai/claude-code" && exit 1)
    cd backend && uv sync
    cd frontend && npm install

# DB 마이그레이션
migrate:
    cd backend && uv run alembic upgrade head

# 테스트
test:
    cd backend && uv run pytest -v

# 코드 포맷·린트
lint:
    cd backend && uv run ruff check . && uv run ruff format .
    cd frontend && npm run lint

# macOS 앱 개발 모드 (Phase 2)
app-dev:
    cd tauri && npm run tauri dev

# macOS 앱 빌드 (Phase 2)
app-build:
    cd tauri && npm run tauri build
```

### 9.3 환경변수 (.env)

```
# Claude CLI 설정
CLAUDE_CLI_PATH=claude                # claude CLI 실행 경로 (PATH에 등록된 경우 기본값)
CLAUDE_CLI_TIMEOUT=120                # Sub-Agent 1회 호출 타임아웃 (초)

# Agent 설정
MAX_SUB_AGENTS=5                      # Team 모드 최대 Sub-Agent 수

# 세션 설정
SESSION_TTL_SECONDS=3600
DB_PATH=./data/coworker.db

# 서버 설정
CORS_ORIGINS=http://localhost:5173    # 프론트엔드 개발 서버 (쉼표 구분으로 복수 지정 가능)
```

### 9.4 backend/pyproject.toml (uv)

```toml
[project]
name = "coworker-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "aiosqlite>=0.20",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.6",
]
```

> **참고**: `anthropic`, `agno`, `ag-ui-protocol` 패키지는 더 이상 필요하지 않다. Claude CLI가 이들을 대체한다. 외부 Python 의존성이 대폭 줄어 관리가 단순해진다.

---

## 10. UI/UX 명세

### 10.1 레이아웃

```
┌─────────────────────────────────────────────────────────────────┐
│  Coworker                               [세션 목록 ☰]  [설정 ⚙]  │
├────────────────────────────┬────────────────────────────────────┤
│                            │                                    │
│   USER CHANNEL             │   AGENT CHANNEL                    │
│   사용자 ↔ Reader           │   Reader ↔ Sub-Agents              │
│                            │   [ Solo 모드: 비활성 / 대기 중 ]    │
│   ┌────────────────────┐   │                                    │
│   │ 🤖 Reader          │   │   ┌──────────────────────────┐    │
│   │ 안녕하세요!         │   │   │  팀 작업이 시작되면        │    │
│   │ 무엇을 도와드릴까요? │   │   │  여기에 Agent 간 대화가   │    │
│   └────────────────────┘   │   │  순차적으로 표시됩니다.   │    │
│                            │   └──────────────────────────┘    │
│   ┌────────────────────┐   │                                    │
│   │        나          │   │                                    │
│   │ ...                │   │                                    │
│   └────────────────────┘   │                                    │
│                            │                                    │
├────────────────────────────┴────────────────────────────────────┤
│  [메시지를 입력하세요...]                          [전송 ↵]        │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Reader 상태 표시

| 상태 | UI 표현 | 설명 |
|------|--------|------|
| `queued` | `⏳ 대기 중... (이전 작업 처리 중)` | 다른 CLI 프로세스 실행 중으로 Lock 대기 |
| `thinking` | `⚙ 분석 중...` (애니메이션) | 복잡도 분류 CLI 실행 중 |
| `solo` | `⏳ 응답 생성 중...` → 완성 응답 표시 | Solo 판단, Agent Channel 비활성 |
| `delegating` | `👥 팀 구성` + Agent 목록 | Team 판단, Agent Channel 활성화 |
| `working` | `⏳ 진행 중... (N/M Agent 완료)` | Sub-Agent 순차 실행 중, 진행률 표시 |
| `integrating` | `📝 결과 통합 중...` | 모든 Sub-Agent 완료 후 통합 CLI 실행 중 |
| `done` | 최종 응답 표시 | 완료, Agent Channel에 전체 내부 대화 표시 |

### 10.3 Agent Channel 메시지 형식

```
┌─────────────────────────────────────┐
│  🔵 Researcher-A  [Researcher]  09:14  │
│  ─────────────────────────────────  │
│  LangGraph Stars 25.2k 확인.        │
│  C1 평가: Supervisor 패턴으로 O.    │
│  FastAPI 통합 패턴 분석 완료.        │
└─────────────────────────────────────┘
```

---

## 11. 개발 단계

### Phase 1: 웹 UI MVP

- [ ] 개발 환경 초기화 (uv, just, FastAPI, React, SQLite, Claude CLI 확인)
- [ ] Claude CLI subprocess 래퍼 구현 (`cli_service.py`, Popen 라인 스트리밍 + `asyncio.to_thread()`)
- [ ] Global Execution Lock 구현 (`asyncio.Lock` 기반 CLI 동시 실행 방지 + 큐잉)
- [ ] Reader Agent 기본 구현 (Solo 모드 + JSON 분류)
- [ ] JSON 파싱 폴백 로직 구현 (F-001a Pydantic 검증 → F-001b 정규식 추출 → F-001c Solo 폴백)
- [ ] REST API 엔드포인트 구현 (채팅, 상태 폴링, Agent Channel 중간 출력 폴링, 취소)
- [ ] User Channel UI 구현 (마크다운 렌더링, 로딩·큐잉 상태 포함)
- [ ] Sub-Agent 5개 프리셋 시스템 프롬프트 구현
- [ ] Team 모드 오케스트레이션 구현 (순차 실행 + Context Assembler 프롬프트 체이닝)
- [ ] Agent Channel UI 구현 (읽기 전용, 실행 중 중간 출력 폴링 표시)
- [ ] 세션 히스토리 저장·복원 (SQLite + WAL 모드)
- [ ] 에러 처리 및 폴백 로직 (CLI 타임아웃, exit code 처리)

### Phase 2: macOS 앱

- [ ] Tauri 프로젝트 초기화 및 웹 UI 임베딩
- [ ] macOS 네이티브 메뉴 및 시스템 트레이 연동
- [ ] 앱 아이콘 및 배포 패키지 (.dmg) 생성
- [ ] 자동 업데이트 기능

---

## 12. 성공 기준

| 기준 | 측정 방법 |
|------|---------|
| Reader Solo/Team 분류 정확도 | 테스트 케이스 20개 중 18개 이상 정확 분류 |
| Solo 응답 지연 | CLI 호출 포함 15초 이내 전체 응답 반환 |
| Team 진행 상태 표시 | 폴링으로 2초 이내에 진행 상태(N/M) 업데이트 표시 |
| Agent Channel 완전성 | 모든 Sub-Agent 결과가 누락 없이 UI에 표시됨 |
| 세션 복원 | 앱 재시작 후 이전 대화 히스토리 완전 복원 |
| macOS 앱 독립 실행 | 빌드 후 `.dmg` 설치만으로 독립 실행 가능 (Claude CLI 사전 설치 전제) |
| 비용 효율 | API 토큰 과금 $0 (Claude 구독만으로 운영) |
