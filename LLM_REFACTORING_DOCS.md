# 다중 LLM 제공자 지원을 위한 리팩토링 및 기능 추가

이 문서는 Coworker 프로젝트에서 단일 Claude CLI 의존성을 벗어나 세션별로 여러 LLM 제공자(LLM Provider) 및 모델을 동적으로 선택할 수 있도록 개선한 내용을 기록합니다.

## 주요 목적
기존 시스템은 AI 응답을 생성하기 위해 무조건 시스템에 설치된 `claude-cli`를 서브프로세스로 호출하도록 하드코딩 되어 있었습니다. 이를 개선하여 향후 OpenAI, Gemini 등 다양한 API를 유연하게 붙일 수 있도록 **구조를 추상화(모듈화)**하고, 프론트엔드 UI를 통해 **사용자가 대화방(세션)별로 원하는 LLM과 모델 버전을 직접 선택**할 수 있게 기능을 추가했습니다.

---

## 상세 변경 내용

### 1. 백엔드 (Backend)

#### 1.1 LLM 팩토리 패턴 도입 및 모듈화
*   **파일 생성:** 
    *   `backend/app/services/llm/base.py`: 모든 LLM 인터페이스가 상속받아야 하는 공통 추상 클래스 `LLMProvider` 정의 (`stream_generate` 비동기 메서드).
    *   `backend/app/services/llm/claude_cli.py`: 기존 `call_claude_streaming` 로직을 감싼 `ClaudeCliProvider` 구현체 작성.
    *   `backend/app/services/llm/__init__.py`: 제공자 이름(예: `"claude-cli"`)에 따라 적절한 `LLMProvider` 객체를 반환하는 `get_provider` 팩토리 함수 제공.

#### 1.2 데이터베이스 스키마 및 마이그레이션
세션별로 어떤 모델을 쓰고 있는지 기억하기 위해 테이블 스키마를 변경했습니다.
*   **모델 변경 (`backend/app/models/db.py`)**: `Session` 테이블에 두 개의 컬럼 추가.
    *   `llm_provider`: (String) 기본값 `"claude-cli"`
    *   `llm_model`: (String, Nullable) 선택적 모델 버전명.
*   **Alembic 마이그레이션**: `alembic revision --autogenerate`를 통해 `f27a2374a8c2_add_llm_provider_and_llm_model.py` 마이그레이션 파일을 생성하고 DB에 반영했습니다.

#### 1.3 Pydantic 스키마 및 서비스 계층 업데이트
*   **스키마 (`backend/app/models/schemas.py`)**: `ChatRequest`, `SessionOut`, `SessionDetail`에 `llm_provider`와 `llm_model` 필드를 추가하여 프론트엔드와 백엔드가 설정값을 주고받을 수 있게 했습니다.
*   **세션 서비스 (`backend/app/services/session_service.py`)**: `create_session` 호출 시 `llm_provider`와 `llm_model` 값을 함께 받아 DB에 저장하도록 수정했습니다.
*   **라우터 (`backend/app/routers/chat.py`)**: `/api/chat` 엔드포인트에서 기존 세션이 있을 경우 요청으로 들어온 LLM 설정이 기존과 다르면 DB의 세션 정보를 업데이트하도록 로직을 추가했습니다. 새로운 세션 생성 시에도 해당 설정값을 넘깁니다.

#### 1.4 Agent 구조의 의존성 주입 (Dependency Injection)
에이전트가 어떤 방식을 쓰든 추상화된 객체만 바라보고 동작하도록 결합도를 낮췄습니다.
*   **`ReaderAgent` (`backend/app/agents/reader.py`)**: 
    *   초기화 시 DB의 세션 정보를 읽어와 `get_provider(provider_name)`를 통해 적절한 LLM 객체를 가져와 저장(`self.llm_provider`)합니다.
    *   모든 AI 호출부(`_solo_respond`, `_integrate_results`, `_summarize_for_context`)를 기존 `call_claude_streaming`에서 `self.llm_provider.stream_generate`로 변경했습니다.
*   **`SubAgent` (`backend/app/agents/sub_agent.py`)**:
    *   초기화 시 `llm_provider` 객체를 주입받도록 생성자를 변경했습니다.
    *   `execute` 메서드 내 AI 실행 부분도 주입받은 provider를 사용하도록 수정되었습니다.

---

### 2. 프론트엔드 (Frontend)

사용자가 LLM 설정을 변경할 수 있는 UI 컨트롤을 추가했습니다.

#### 2.1 API 타입 동기화
*   **`frontend/src/types/api.ts`**: API 요청/응답 객체에 `llm_provider`, `llm_model` 옵셔널 필드를 추가했습니다.

#### 2.2 UI 컴포넌트 업데이트
*   **헤더 UI 변경 (`frontend/src/App.tsx`)**: 
    *   대화방 상단 헤더 우측에 `Provider`를 선택할 수 있는 Dropdown(`select`)과 모델 이름을 입력받을 수 있는 Input 텍스트 필드를 추가했습니다.
    *   상태 관리 변수 `llmProvider`, `llmModel`을 선언하고, 선택된 세션(`currentSession`)이 바뀔 때마다 해당 세션의 정보로 UI가 동기화되도록 `useEffect`를 추가했습니다.
*   **사용자 채널 (`frontend/src/components/UserChannel/index.tsx`)**:
    *   Props로 `llmProvider`와 `llmModel`을 받아, 사용자가 "전송" 버튼을 눌러 API `api.chat()`을 호출할 때 해당 설정값을 백엔드로 함께 전달하도록 로직을 변경했습니다.

---

## 향후 확장 방법 (How to Extend)
새로운 LLM(예: OpenAI API)을 추가하려면 다음 작업만 수행하면 됩니다.

1.  `backend/app/services/llm/openai_api.py` 와 같이 새로운 파일을 만들고 `LLMProvider`를 상속받는 `OpenAIProvider` 클래스를 구현합니다.
2.  `backend/app/services/llm/__init__.py`의 `_providers` 딕셔너리에 `"openai": OpenAIProvider()`를 매핑합니다.
3.  `frontend/src/App.tsx`의 Dropdown `<select>`에 `<option value="openai">OpenAI</option>` 태그를 추가합니다.