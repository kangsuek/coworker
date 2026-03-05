"""분류 서비스.

규칙 기반 분류 (classify_message): CLI 호출 없이 즉시 결정.
JSON 파싱 폴백 체인 (parse_classification): CLI 출력 파싱용 레거시 유지.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.config import settings
from app.models.schemas import AgentPlan, ClassificationResult

# ── 규칙 기반 분류 ──────────────────────────────────────────────────────────


def _role_for_task(task: str) -> str:
    """태스크 텍스트에서 적합한 Agent 역할 결정.

    순서 및 키워드는 settings.role_map에서 결정 (환경변수로 재정의 가능).
    """
    for role, keywords in settings.role_map:
        if any(kw in task for kw in keywords):
            return role
    return "Researcher"


def classify_message(user_message: str) -> ClassificationResult:
    """규칙 기반 Solo/Team 분류. CLI 호출 없이 즉시 결정.

    판정 기준:
    - TEAM_TRIGGER_HEADER 값으로 시작하는 메시지 → team 시도
      - 헤더 이후 번호 목록 2개 이상이면 team, 미만이면 solo fallback
    - 그 외 → solo
    """
    header = settings.team_trigger_header.strip()

    if not (header and user_message.startswith(header)):
        return ClassificationResult(
            mode="solo",
            reason="단순 요청",
            agents=[],
            user_status_message=None,
        )

    # 헤더 이후 텍스트에서 번호 목록 추출: "1. task", "1) task", "2.task" 형태
    body = user_message[len(header):].strip()
    raw_items = re.findall(r"\d+[.)]\s*(.+?)(?=,?\s*\d+[.)]|$|\n)", body)
    numbered_items = [t.strip().strip(",").strip() for t in raw_items if t.strip()]

    # 에이전트 구성 (최대 5개)
    agents: list[AgentPlan] = []
    for i, task in enumerate(numbered_items[:5]):
        # 기본적으로 순차적 의존성(Sequential) 설정: i번은 i-1번에 의존
        deps = [i - 1] if i > 0 else []
        agents.append(AgentPlan(role=_role_for_task(task), task=task, depends_on=deps))

    if len(agents) < 2:
        return ClassificationResult(
            mode="solo",
            reason="에이전트 구성 불가 (태스크 목록 부족)",
            agents=[],
            user_status_message=None,
        )

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
