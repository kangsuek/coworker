# LLM 리팩토링 조사 보고서

## 1) 조사 범위 및 방법
- 기준 문서: `LLM_REFACTORING_DOCS.md`
- 실제 구현 대조 파일:
  - 백엔드: `backend/app/routers/chat.py`, `backend/app/routers/sessions.py`, `backend/app/agents/reader.py`, `backend/app/agents/sub_agent.py`, `backend/app/models/db.py`, `backend/app/models/schemas.py`, `backend/app/services/session_service.py`, `backend/app/services/llm/*`, `backend/migrations/versions/f27a2374a8c2_add_llm_provider_and_llm_model.py`
  - 프론트엔드: `frontend/src/App.tsx`, `frontend/src/components/UserChannel/index.tsx`, `frontend/src/hooks/useSession.ts`, `frontend/src/types/api.ts`, `frontend/src/lib/api.ts`
- 검증 시도:
  - 백엔드 테스트 실행 불가(환경에 `pytest` 미설치)
  - 프론트 빌드 실행 결과: 타입 오류 1건 재현
    - `src/hooks/useSession.ts(89,11): Type ... is missing llm_provider, llm_model`

## 2) 문서상 의도된 흐름 요약
1. 사용자가 UI에서 `llm_provider`, `llm_model` 선택
2. `POST /api/chat` 요청 시 설정값 전달
3. 세션 생성/갱신 시 DB `sessions.llm_provider`, `sessions.llm_model` 저장
4. `ReaderAgent`가 세션에서 제공자/모델 조회 후 LLM 호출
5. Solo/Team 모두 provider 추상화(`LLMProvider.stream_generate`)를 통해 실행
6. 세션 조회 API와 프론트 상태가 해당 설정을 지속적으로 동기화

## 3) 발견된 버그 (치명도 순)

### [Critical] 세션 API 응답 스키마 불일치로 런타임 500 가능
- 위치: `backend/app/routers/sessions.py`
- 원인:
  - `SessionOut`, `SessionDetail` 스키마는 `llm_provider`, `llm_model`을 필수로 요구
  - 그런데 라우터 반환 시 두 필드를 누락
- 영향:
  - `GET /api/sessions`, `POST /api/sessions`, `GET /api/sessions/{id}`에서 응답 모델 검증 실패 가능
  - 세션 목록/상세/생성의 핵심 기능이 깨질 수 있음
- 근거 코드:
```23:35:backend/app/routers/sessions.py
    return [
        SessionOut(id=s.id, title=s.title, created_at=s.created_at, updated_at=s.updated_at)
        for s in sessions
    ]
...
    return SessionOut(
        id=sess.id, title=sess.title, created_at=sess.created_at, updated_at=sess.updated_at
    )
```
```88:111:backend/app/models/schemas.py
class SessionOut(BaseModel):
    id: str
    title: str | None
    llm_provider: str
    llm_model: str | None
    created_at: UTCDatetime
    updated_at: UTCDatetime
```
- 권장 수정:
  - `sessions.py`의 모든 `SessionOut`, `SessionDetail` 생성부에 `llm_provider`, `llm_model` 명시 추가
  - 세션 API 테스트에 해당 필드 존재 assert 추가

### [High] 프론트 타입 오류로 빌드 실패
- 위치: `frontend/src/hooks/useSession.ts`
- 원인:
  - `Session` 타입에 `llm_provider`, `llm_model`이 필수가 되었는데 pseudo session 객체에 누락
- 재현:
  - `frontend`에서 `npm run -s build` 실행 시 실패
- 근거 코드:
```88:99:frontend/src/hooks/useSession.ts
  const setCurrentSessionFromChat = useCallback((sessionId: string) => {
    const pseudo: Session = {
      id: sessionId,
      title: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
```
- 영향:
  - CI/로컬 빌드 파이프라인 차단
  - 타입 안정성 붕괴
- 권장 수정:
  - pseudo 객체에 기본값 추가
    - `llm_provider: 'claude-cli'`
    - `llm_model: null`

### [High] 실행 상태 API가 실제 선택 모델 대신 전역 기본 모델을 반환
- 위치: `backend/app/routers/chat.py`
- 원인:
  - `GET /api/runs/{run_id}`의 `model` 계산이 `settings.solo_model/settings.team_model` 기반
  - 실제 실행은 `ReaderAgent`에서 세션별 `session.llm_model` 우선 사용
- 결과:
  - UI 상태 배지(`StatusBadge`)에 표시되는 모델과 실제 실행 모델이 달라질 수 있음
- 근거 코드:
```78:82:backend/app/routers/chat.py
    model = (
        settings.solo_model or None if run.mode == "solo"
        else settings.team_model or None if run.mode == "team"
        else None
    )
```
```190:195:backend/app/agents/reader.py
        model_to_use = self.session_model or settings.solo_model
        return await self.llm_provider.stream_generate(
            self.SOLO_SYSTEM_PROMPT,
            prompt,
            model=model_to_use,
```
- 권장 수정:
  - `Run` 조회 시 `Session`을 함께 조회하여 `session.llm_model`을 우선 반환
  - 필요 시 run 생성 시점에 `effective_model`을 run에 저장해 이력 정확성 확보

### [Medium] 미지원 provider 값이 DB에 저장되지만 실제 실행은 조용히 fallback
- 위치: `backend/app/routers/chat.py`, `backend/app/services/llm/__init__.py`
- 원인:
  - 입력 provider 검증 없음
  - `get_provider()`는 unknown name에 대해 `claude-cli`로 묵시 fallback
- 영향:
  - DB/프론트 표시 값과 실제 실행 provider가 불일치
  - 디버깅 난이도 증가, 사용자 혼란
- 근거 코드:
```11:13:backend/app/services/llm/__init__.py
def get_provider(name: str) -> LLMProvider:
    """이름에 해당하는 LLM Provider를 반환합니다. 기본값은 claude-cli입니다."""
    return _providers.get(name, _providers["claude-cli"])
```
- 권장 수정:
  - 허용 provider 목록 검증(백엔드 422 반환)
  - 또는 fallback 발생 시 경고 로깅 + 세션값 자동 정정

## 4) 개선사항 (버그 예방/운영 안정성)

### A. 테스트 보강 (가장 우선)
- 세션 API 테스트에 아래 항목 추가:
  - `llm_provider`, `llm_model` 존재/값 검증
  - `POST /api/chat` 후 세션 조회 시 설정 반영 여부
  - `GET /api/runs/{id}` 모델 표기와 실제 실행 모델 일치 여부
- 현재 누락된 계약 테스트가 있어 스키마 회귀가 쉽게 유입됨

### B. provider 레지스트리 개선
- 현재 provider 인스턴스를 전역 singleton 딕셔너리로 보관
- 현재 구현은 무상태라 문제 없지만, 추후 provider가 상태를 가지면 세션 간 간섭 위험
- 개선:
  - 팩토리에 class 또는 factory callable 등록 후 요청마다 인스턴스 생성
  - 혹은 provider 무상태 계약을 명문화

### C. API 계약 명확화
- `POST /api/chat`에서 잘못된 `session_id`가 들어오면 새 세션 생성됨(암묵적 동작)
- 의도된 동작인지 명시 필요
  - 옵션 1) 현재 유지 + 문서화
  - 옵션 2) 404 반환으로 명시적 실패

### D. 마이그레이션/모델 일관성 보강
- `llm_provider`는 non-null + server_default로 적절
- 다만 기존 데이터/운영 환경에서 provider/model 검증 제약이 없음
- 개선:
  - 앱 레벨 검증 + 선택적으로 DB 체크 제약(가능한 DB인 경우)

## 5) 우선순위 액션 플랜
1. `sessions.py` 응답 필드 누락 수정 (Critical)
2. `useSession.ts` pseudo session 타입 수정 (High)
3. run status 모델 계산 로직 수정 (High)
4. provider 입력 검증 추가 + 에러 메시지 정의 (Medium)
5. 회귀 테스트 추가 (A 항목 전체)

## 6) 결론
- 문서의 리팩토링 방향(Provider 추상화, 세션별 모델 선택)은 구조적으로 타당함
- 그러나 현재 상태는 **세션 API 응답 스키마 누락 + 프론트 타입 불일치**로 인해 실제 사용/배포 단계에서 즉시 문제를 일으킬 가능성이 큼
- 위 1~3번 우선 수정 후 테스트를 보강해야 안정적으로 다중 LLM 확장이 가능함
