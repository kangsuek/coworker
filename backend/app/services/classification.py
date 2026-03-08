"""분류 서비스.

규칙 기반 분류 (classify_message): CLI 호출 없이 즉시 결정.
JSON 파싱 폴백 체인 (parse_classification): CLI 출력 파싱용 레거시 유지.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.config import settings
from app.models.schemas import AgentPlan, ClassificationResult, LLMClassificationResponse
from app.services.llm import get_provider
from app.services.llm.base import LLMProvider

# ── 규칙 기반 분류 ──────────────────────────────────────────────────────────

_EXPLICIT_ROLE_RE = re.compile(r"^\[([^\]]+)\]\s*")


def _parse_explicit_role(task: str) -> tuple[str, str | None]:
    """태스크 텍스트에서 [역할명] 프리픽스 추출.

    Returns:
        (태스크 본문, 역할명 or None)
    """
    m = _EXPLICIT_ROLE_RE.match(task)
    if m:
        return task[m.end():].strip(), m.group(1).strip()
    return task, None


def _role_for_task(task: str) -> str:
    """태스크 텍스트에서 적합한 Agent 역할 결정.

    순서 및 키워드는 settings.role_map에서 결정 (환경변수로 재정의 가능).
    """
    for role, keywords in settings.role_map:
        if any(kw in task for kw in keywords):
            return role
    return "Researcher"


async def _classify_with_llm(
    user_message: str,
    current_agents: list[AgentPlan],
    provider: LLMProvider,
    model: str = "",
    custom_roles: dict[str, str] | None = None,
    explicit_roles: dict[int, str] | None = None,
) -> list[AgentPlan]:
    """LLM을 사용하여 태스크의 역할과 의존성을 정교화합니다."""

    # 가용한 역할 목록 및 설명 (기본 역할 + 세션 커스텀 역할)
    base_roles = [
        ("Researcher", settings.role_researcher_keywords),
        ("Writer", settings.role_writer_keywords),
        ("Planner", settings.role_planner_keywords),
        ("Coder", settings.role_coder_keywords),
        ("Reviewer", settings.role_reviewer_keywords),
    ]
    role_info_lines = [f"- {role}: {keywords}" for role, keywords in base_roles]
    if custom_roles:
        for role_name, prompt in custom_roles.items():
            role_info_lines.append(f"- {role_name}: {prompt[:60]}...")
    role_info = "\n".join(role_info_lines)

    # 명시적으로 지정된 역할은 LLM에게 변경 금지 안내
    locked_info = ""
    if explicit_roles:
        locked_lines = [f"  - 태스크 {i}: '{r}' (변경 불가)" for i, r in explicit_roles.items()]
        locked_info = "\n\n[명시된 역할 — 반드시 유지]\n" + "\n".join(locked_lines)

    # 태스크 리스트 포맷팅
    tasks_str = "\n".join([f"{i}. {a.task}" for i, a in enumerate(current_agents)])

    system_prompt = f"""당신은 멀티 에이전트 시스템의 Planner입니다. 사용자의 요청과 태스크 목록을 분석하여 각 태스크에 가장 적합한 'role'과 'depends_on'을 JSON으로 응답하십시오.

[역할 정의]
{role_info}{locked_info}

[의존성 규칙]
- 앞선 태스크의 결과가 필요한 경우 해당 인덱스(0부터 시작)를 'depends_on'에 추가.
- 단순 순차 작업이 아닌 실제 데이터 흐름에 따라 설정.

[출력 형식]
{{"agents": [{{ "role": "역할", "task": "내용", "depends_on": [인덱스] }}]}}
다른 설명 없이 JSON만 반환하십시오."""

    user_prompt = f"사용자 메시지: {user_message}\n태스크 목록:\n{tasks_str}"

    try:
        # LLM 호출 (경량 분류 전용 모델 사용)
        raw_response = await provider.stream_generate(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model=model,
        )

        # JSON 추출 및 파싱
        # (주의: _extract_json_objects는 이 파일 하단에 정의됨)
        candidates = _extract_json_objects(raw_response)
        
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                # LLMClassificationResponse를 통한 검증 및 인스턴스화
                response_obj = LLMClassificationResponse(**data)
                
                # 결과 반영
                num_tasks = len(current_agents)
                for agent in response_obj.agents:
                    # 인덱스가 범위를 벗어나지 않도록 필터링
                    agent.depends_on = [idx for idx in agent.depends_on if 0 <= idx < num_tasks]
                
                # 명시된 역할은 LLM이 변경해도 원래 값으로 복원
                result = response_obj.agents
                if explicit_roles:
                    for idx, role_name in explicit_roles.items():
                        if idx < len(result):
                            result[idx].role = role_name

                # BUG-H01: LLM이 원본보다 적은 에이전트를 반환하면 태스크 누락 → 원본 유지
                if len(result) < len(current_agents):
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "LLM 분류 에이전트 수 불일치 (원본=%d, LLM=%d), 원본 유지",
                        len(current_agents), len(result),
                    )
                    return current_agents

                return result
            except (json.JSONDecodeError, ValidationError):
                continue

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"LLM Classification failed: {e}")
        raise

    return current_agents


async def classify_message(
    user_message: str,
    llm_provider: LLMProvider | None = None,
    classify_model: str = "",
    custom_roles: dict[str, str] | None = None,
) -> ClassificationResult:
    """Solo/Team 분류 및 지능형 태스크 분석.

    1. 규칙 기반으로 Solo/Team 결정 및 1차 태스크 분할.
    2. Team 모드일 경우 LLM을 통해 역할(Role) 및 의존성(Dependency) 강화.
    """
    header = settings.team_trigger_header.strip()

    if not (header and user_message.startswith(header)):
        return ClassificationResult(
            mode="solo",
            reason="단순 요청",
            agents=[],
            user_status_message=None,
        )

    # 헤더 이후 텍스트에서 번호 목록 추출
    body = user_message[len(header):].strip()
    raw_items = re.findall(r"\d+[.)]\s*(.+?)(?=,?\s*\d+[.)]|$|\n)", body)
    numbered_items = [t.strip().strip(",").strip() for t in raw_items if t.strip()]

    # 1차 에이전트 구성 (최대 5개, 기본적으로 순차적)
    agents: list[AgentPlan] = []
    explicit_roles: dict[int, str] = {}  # index -> 명시된 역할명
    for i, task in enumerate(numbered_items[:5]):
        task_body, explicit_role = _parse_explicit_role(task)
        if explicit_role:
            role = explicit_role
            explicit_roles[i] = explicit_role
        else:
            task_body = task
            role = _role_for_task(task)
        depends_on = [i - 1] if i > 0 else []
        agents.append(AgentPlan(role=role, task=task_body, depends_on=depends_on))

    if len(agents) < 2:
        return ClassificationResult(
            mode="solo",
            reason="에이전트 구성 불가 (태스크 목록 부족)",
            agents=[],
            user_status_message=None,
        )

    # 2단계: LLM을 통한 역할 및 의존성 강화
    provider = llm_provider or get_provider("gemini-cli")
    try:
        enhanced_agents = await _classify_with_llm(
            user_message, agents, provider, classify_model, custom_roles, explicit_roles
        )
        agents = enhanced_agents
    except Exception:
        # LLM 실패 시 1차 구성(규칙 기반) 유지 (Fallback)
        pass

    return ClassificationResult(
        mode="team",
        reason=f"다단계 작업 ({len(agents)}개 전문 분야 필요)",
        agents=agents,
        user_status_message=None,
    )


# ── JSON 파싱 폴백 체인 (레거시 — CLI 출력 파싱용) ──────────────────────────


def _extract_json_objects(text: str) -> list[str]:
    """중괄호 카운팅으로 JSON 객체 후보 문자열 추출.

    정규식과 달리 임의 깊이의 중첩 JSON을 정확히 추출한다.
    """
    results: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                results.append(text[start : i + 1])
                start = -1
    return results


def parse_classification(raw_output: str) -> ClassificationResult:
    """CLI 출력을 ClassificationResult로 변환. 4단계 폴백."""
    # 0단계: CLI --output-format json 래퍼 처리
    try:
        wrapper = json.loads(raw_output)
        if isinstance(wrapper, dict) and "result" in wrapper:
            result_val = wrapper["result"]
            if isinstance(result_val, str):
                raw_output = result_val
            elif isinstance(result_val, dict):
                try:
                    return ClassificationResult(**result_val)
                except ValidationError:
                    pass
    except json.JSONDecodeError:
        pass

    # 1단계 (F-001a): 직접 JSON 파싱 + Pydantic 검증
    try:
        data = json.loads(raw_output)
        return ClassificationResult(**data)
    except (json.JSONDecodeError, ValidationError):
        pass

    # 2단계 (F-001b): 중괄호 카운팅으로 JSON 블록들 추출, 각각 파싱 시도
    for candidate in _extract_json_objects(raw_output):
        try:
            data = json.loads(candidate)
            return ClassificationResult(**data)
        except (json.JSONDecodeError, ValidationError):
            continue

    # 3단계 (F-001c): Solo 폴백
    return ClassificationResult(
        mode="solo",
        reason="파싱 실패: CLI 출력을 분류 결과로 변환할 수 없음",
        agents=[],
        user_status_message=None,
    )
