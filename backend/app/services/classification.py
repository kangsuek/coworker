"""분류 서비스.

규칙 기반 분류 (classify_message): CLI 호출 없이 즉시 결정.
JSON 파싱 폴백 체인 (parse_classification): CLI 출력 파싱용 레거시 유지.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.models.schemas import AgentPlan, ClassificationResult

# ── 규칙 기반 분류 ──────────────────────────────────────────────────────────

_TEAM_TRIGGER_KEYWORDS = [
    "각각", "전문가", "팀프로젝트", "팀 프로젝트", "단계별", "분야별",
    "다단계", "여러 분야", "각 전문가",
]

# 역할별 키워드: 먼저 매칭된 역할로 결정 (순서가 우선순위)
# Writer를 Planner보다 먼저 배치 — "마케팅 계획" 처럼 도메인 키워드가 "계획"보다 우선
_ROLE_MAP: list[tuple[str, list[str]]] = [
    ("Researcher", ["조사", "리서치", "분석", "시장", "경쟁사", "데이터 수집", "현황", "정보 수집"]),
    ("Writer",     ["마케팅", "홍보", "카피", "콘텐츠", "글쓰기", "작성", "문서", "보고서"]),
    ("Planner",    ["전략", "기획", "투자", "유치", "계획", "로드맵", "설계", "아키텍처"]),
    ("Coder",      ["코드", "구현", "개발", "프로그래밍", "기술", "빌드"]),
    ("Reviewer",   ["리뷰", "검토", "테스트", "감사", "검증", "평가", "피드백"]),
]


def _role_for_task(task: str) -> str:
    """태스크 텍스트에서 적합한 Agent 역할 결정."""
    for role, keywords in _ROLE_MAP:
        if any(kw in task for kw in keywords):
            return role
    return "Researcher"


def classify_message(user_message: str) -> ClassificationResult:
    """규칙 기반 Solo/Team 분류. CLI 호출 없이 즉시 결정.

    판정 기준:
    - 번호 목록 3개 이상 → team
    - 팀/전문가/각각 등 키워드 포함 → team
    - 그 외 → solo
    """
    # 번호 목록 추출: "1. task", "1) task", "2.task" 형태
    raw_items = re.findall(r"\d+[.)]\s*(.+?)(?=,?\s*\d+[.)]|$|\n)", user_message.strip())
    numbered_items = [t.strip().strip(",").strip() for t in raw_items if t.strip()]

    has_team_keyword = any(kw in user_message for kw in _TEAM_TRIGGER_KEYWORDS)
    is_team = len(numbered_items) >= 3 or has_team_keyword

    if not is_team:
        return ClassificationResult(
            mode="solo",
            reason="단순 요청",
            agents=[],
            user_status_message=None,
        )

    # 번호 목록에서 에이전트 생성 (최대 5개)
    agents: list[AgentPlan] = [
        AgentPlan(role=_role_for_task(task), task=task)
        for task in numbered_items[:5]
    ]

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
