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

# ── 규칙 기반 분류 ──────────────────────────────────────────────────────────


def _role_for_task(task: str) -> str:
    """태스크 텍스트에서 적합한 Agent 역할 결정.

    순서 및 키워드는 settings.role_map에서 결정 (환경변수로 재정의 가능).
    """
    for role, keywords in settings.role_map:
        if any(kw in task for kw in keywords):
            return role
    return "Researcher"


async def _classify_with_llm(user_message: str, current_agents: list[AgentPlan]) -> list[AgentPlan]:
    """LLM을 사용하여 태스크의 역할과 의존성을 정교화합니다."""
    # LLM 프로바이더 획득 (기본값: gemini-cli)
    provider = get_provider("gemini-cli")

    # 가용한 역할 목록 및 설명
    role_info = "\n".join([f"- {role}: {keywords}" for role, keywords in [
        ("Researcher", settings.role_researcher_keywords),
        ("Writer", settings.role_writer_keywords),
        ("Planner", settings.role_planner_keywords),
        ("Coder", settings.role_coder_keywords),
        ("Reviewer", settings.role_reviewer_keywords),
    ]])

    # 태스크 리스트 포맷팅
    tasks_str = "\n".join([f"{i}. {a.task}" for i, a in enumerate(current_agents)])

    system_prompt = f"""당신은 멀티 에이전트 시스템의 Planner입니다. 사용자의 요청과 태스크 목록을 분석하여 각 태스크에 가장 적합한 'role'과 'depends_on'을 JSON으로 응답하십시오.

[역할 정의]
{role_info}

[의존성 규칙]
- 앞선 태스크의 결과가 필요한 경우 해당 인덱스(0부터 시작)를 'depends_on'에 추가.
- 단순 순차 작업이 아닌 실제 데이터 흐름에 따라 설정.

[출력 형식]
{{"agents": [{{ "role": "역할", "task": "내용", "depends_on": [인덱스] }}]}}
다른 설명 없이 JSON만 반환하십시오."""

    user_prompt = f"사용자 메시지: {user_message}\n태스크 목록:\n{tasks_str}"

    try:
        # LLM 호출
        raw_response = await provider.stream_generate(
            system_prompt=system_prompt,
            user_message=user_prompt,
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
                
                # 원본 태스크 내용이 LLM에 의해 변조되었을 경우를 대비해 순서대로 매칭 (옵션)
                # 여기서는 LLM이 반환한 agents 리스트를 신뢰함
                return response_obj.agents
            except (json.JSONDecodeError, ValidationError):
                continue

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"LLM Classification failed: {e}")
        raise

    return current_agents


async def classify_message(user_message: str) -> ClassificationResult:
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
    for i, task in enumerate(numbered_items[:5]):
        depends_on = [i - 1] if i > 0 else []
        agents.append(AgentPlan(role=_role_for_task(task), task=task, depends_on=depends_on))

    if len(agents) < 2:
        return ClassificationResult(
            mode="solo",
            reason="에이전트 구성 불가 (태스크 목록 부족)",
            agents=[],
            user_status_message=None,
        )

    # 2단계: LLM을 통한 역할 및 의존성 강화
    try:
        enhanced_agents = await _classify_with_llm(user_message, agents)
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
