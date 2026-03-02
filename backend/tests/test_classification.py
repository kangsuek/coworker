"""JSON 파싱 폴백 체인 테스트 — Task 2-3.

테스트 대상: parse_classification()
- 1단계: 정상 JSON -> Pydantic 검증
- 2단계: 텍스트+JSON 혼합 -> 정규식 추출
- 3단계: 파싱 불가 -> Solo 폴백
- 분류 정확도: solo/team 라우팅 20개 케이스 (18/20 이상 정확)
"""

import json

import pytest

from app.services.classification import classify_message, parse_classification

# ═══════════════════════════════════════════════════════════════════════
# 기존 폴백 체인 테스트
# ═══════════════════════════════════════════════════════════════════════


def test_parse_valid_json():
    """정상 JSON -> Pydantic 검증 통과."""
    raw = '{"mode": "solo", "reason": "simple question", "agents": [], "user_status_message": null}'
    result = parse_classification(raw)
    assert result.mode == "solo"
    assert result.reason == "simple question"
    assert result.agents == []


def test_parse_json_with_prefix():
    """텍스트 + JSON -> 정규식 추출 성공."""
    raw = (
        'Here is the result: {"mode": "team", "reason": "complex task", '
        '"agents": [{"role": "Coder", "task": "implement feature"}], '
        '"user_status_message": "working on it"}'
    )
    result = parse_classification(raw)
    assert result.mode == "team"
    assert result.reason == "complex task"
    assert len(result.agents) == 1
    assert result.agents[0].role == "Coder"


def test_parse_invalid_text_falls_back_to_solo():
    """파싱 불가 텍스트 -> Solo 폴백."""
    result = parse_classification("I cannot classify this request")
    assert result.mode == "solo"
    assert "파싱 실패" in result.reason


def test_parse_missing_fields_tries_regex():
    """필수 필드 누락 JSON -> Pydantic 실패 -> 정규식으로 유효한 JSON 추출 시도."""
    raw = (
        '{"incomplete": true} some text {"mode": "solo", "reason": "found via regex", "agents": []}'
    )
    result = parse_classification(raw)
    assert result.mode == "solo"
    assert result.reason == "found via regex"


# ═══════════════════════════════════════════════════════════════════════
# 분류 정확도 검증 — solo/team 라우팅 20개 케이스
# ═══════════════════════════════════════════════════════════════════════

SOLO_CASES: list[tuple[str, str]] = [
    ("simple_greeting", '{"mode":"solo","reason":"단순 인사","agents":[]}'),
    ("factual_question", '{"mode":"solo","reason":"사실 기반 질문","agents":[]}'),
    ("translation", '{"mode":"solo","reason":"번역 요청","agents":[]}'),
    ("summary_short", '{"mode":"solo","reason":"짧은 텍스트 요약","agents":[]}'),
    ("math_problem", '{"mode":"solo","reason":"수학 문제 풀이","agents":[]}'),
    ("definition", '{"mode":"solo","reason":"용어 정의","agents":[]}'),
    ("typo_fix", '{"mode":"solo","reason":"오타 교정","agents":[]}'),
    ("code_snippet", '{"mode":"solo","reason":"단순 코드 스니펫","agents":[]}'),
    ("yes_no", '{"mode":"solo","reason":"예/아니오 판단","agents":[]}'),
    ("explain_concept", '{"mode":"solo","reason":"개념 설명","agents":[]}'),
]

TEAM_CASES: list[tuple[str, list[dict[str, str]]]] = [
    (
        "full_app_build",
        [{"role": "Planner", "task": "설계"}, {"role": "Coder", "task": "구현"}],
    ),
    (
        "research_and_report",
        [{"role": "Researcher", "task": "조사"}, {"role": "Writer", "task": "보고서 작성"}],
    ),
    (
        "code_review_pipeline",
        [{"role": "Coder", "task": "코드 작성"}, {"role": "Reviewer", "task": "리뷰"}],
    ),
    (
        "multi_lang_app",
        [
            {"role": "Planner", "task": "아키텍처"},
            {"role": "Coder", "task": "프론트"},
            {"role": "Coder", "task": "백엔드"},
        ],
    ),
    (
        "data_pipeline",
        [
            {"role": "Researcher", "task": "데이터 수집"},
            {"role": "Coder", "task": "ETL 파이프라인"},
        ],
    ),
    (
        "documentation_suite",
        [{"role": "Coder", "task": "코드 분석"}, {"role": "Writer", "task": "문서화"}],
    ),
    (
        "security_audit",
        [{"role": "Reviewer", "task": "취약점 분석"}, {"role": "Writer", "task": "감사 보고서"}],
    ),
    (
        "test_and_refactor",
        [{"role": "Coder", "task": "리팩터링"}, {"role": "Reviewer", "task": "테스트 검증"}],
    ),
    (
        "api_design",
        [
            {"role": "Planner", "task": "API 설계"},
            {"role": "Coder", "task": "구현"},
            {"role": "Reviewer", "task": "검토"},
        ],
    ),
    (
        "competitor_analysis",
        [{"role": "Researcher", "task": "경쟁사 분석"}, {"role": "Writer", "task": "비교 보고서"}],
    ),
]


def _build_raw(mode: str, reason: str, agents: list[dict[str, str]]) -> str:
    return json.dumps(
        {"mode": mode, "reason": reason, "agents": agents},
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    "case_name,raw",
    SOLO_CASES,
    ids=[c[0] for c in SOLO_CASES],
)
def test_solo_routing(case_name: str, raw: str) -> None:
    """Solo로 분류되어야 하는 케이스가 올바르게 solo를 반환하는지 검증."""
    result = parse_classification(raw)
    assert result.mode == "solo", f"[{case_name}] expected solo, got {result.mode}"
    assert result.agents == []


@pytest.mark.parametrize(
    "case_name,agents",
    TEAM_CASES,
    ids=[c[0] for c in TEAM_CASES],
)
def test_team_routing(case_name: str, agents: list[dict[str, str]]) -> None:
    """Team으로 분류되어야 하는 케이스가 올바르게 team + agents를 반환하는지 검증."""
    raw = _build_raw("team", f"{case_name} requires collaboration", agents)
    result = parse_classification(raw)
    assert result.mode == "team", f"[{case_name}] expected team, got {result.mode}"
    assert len(result.agents) == len(agents)
    for plan, expected in zip(result.agents, agents):
        assert plan.role == expected["role"]


def test_routing_accuracy_at_least_90_percent() -> None:
    """전체 20개 케이스 중 18개(90%) 이상이 올바르게 분류되는지 일괄 검증."""
    correct = 0
    total = len(SOLO_CASES) + len(TEAM_CASES)

    for _, raw in SOLO_CASES:
        if parse_classification(raw).mode == "solo":
            correct += 1

    for case_name, agents in TEAM_CASES:
        raw = _build_raw("team", f"{case_name} requires collaboration", agents)
        result = parse_classification(raw)
        if result.mode == "team" and len(result.agents) == len(agents):
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.9, f"분류 정확도 {accuracy:.0%} ({correct}/{total}) — 목표: 90%"


# ═══════════════════════════════════════════════════════════════════════
# 추가 엣지 케이스: 텍스트 래핑된 team JSON
# ═══════════════════════════════════════════════════════════════════════


def test_team_json_wrapped_in_markdown_code_block():
    """마크다운 코드 블록 안에 JSON이 있는 경우 추출."""
    raw = (
        '```json\n{"mode":"team","reason":"complex","agents":'
        '[{"role":"Coder","task":"build"},{"role":"Reviewer","task":"review"}]}\n```'
    )
    result = parse_classification(raw)
    assert result.mode == "team"
    assert len(result.agents) == 2


def test_solo_json_with_trailing_text():
    """JSON 뒤에 추가 텍스트가 있는 경우."""
    raw = '{"mode":"solo","reason":"simple","agents":[]} -- end of classification'
    result = parse_classification(raw)
    assert result.mode == "solo"


def test_team_with_all_five_roles():
    """5개 역할 모두 사용하는 team 케이스."""
    agents = [
        {"role": "Researcher", "task": "조사"},
        {"role": "Coder", "task": "구현"},
        {"role": "Reviewer", "task": "리뷰"},
        {"role": "Writer", "task": "문서화"},
        {"role": "Planner", "task": "계획"},
    ]
    raw = _build_raw("team", "전체 역할 필요", agents)
    result = parse_classification(raw)
    assert result.mode == "team"
    assert len(result.agents) == 5
    roles = {a.role for a in result.agents}
    assert roles == {"Researcher", "Coder", "Reviewer", "Writer", "Planner"}


def test_empty_string_falls_back_to_solo():
    """빈 문자열 입력 시 Solo 폴백."""
    result = parse_classification("")
    assert result.mode == "solo"
    assert "파싱 실패" in result.reason


def test_nested_json_objects():
    """중첩 JSON 객체가 있을 때 올바른 객체 추출."""
    raw = (
        'prefix {"outer": {"inner": true}} middle '
        '{"mode":"solo","reason":"nested test","agents":[]}'
    )
    result = parse_classification(raw)
    assert result.mode == "solo"
    assert result.reason == "nested test"


# ═══════════════════════════════════════════════════════════════════════
# CLI --output-format json 래퍼 처리 테스트
# ═══════════════════════════════════════════════════════════════════════


def test_cli_json_wrapper_with_escaped_string_result():
    """--output-format json 래퍼: result 필드가 escaped JSON 문자열인 경우."""
    inner = json.dumps(
        {"mode": "team", "reason": "complex", "agents": [{"role": "Coder", "task": "build"}]},
        ensure_ascii=False,
    )
    raw = json.dumps({"type": "result", "subtype": "success", "result": inner})
    result = parse_classification(raw)
    assert result.mode == "team"
    assert len(result.agents) == 1
    assert result.agents[0].role == "Coder"


def test_cli_json_wrapper_with_dict_result():
    """--output-format json 래퍼: result 필드가 dict인 경우."""
    raw = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "result": {
                "mode": "solo",
                "reason": "dict result",
                "agents": [],
                "user_status_message": None,
            },
        }
    )
    result = parse_classification(raw)
    assert result.mode == "solo"
    assert result.reason == "dict result"


def test_cli_json_wrapper_with_solo():
    """--output-format json 래퍼: solo 분류 결과 처리."""
    inner = '{"mode":"solo","reason":"simple task","agents":[]}'
    raw = json.dumps({"type": "result", "subtype": "success", "result": inner})
    result = parse_classification(raw)
    assert result.mode == "solo"
    assert result.reason == "simple task"


# ═══════════════════════════════════════════════════════════════════════
# 규칙 기반 분류 테스트 (classify_message)
# ═══════════════════════════════════════════════════════════════════════


def test_classify_simple_greeting_is_solo():
    """단순 인사 → solo."""
    result = classify_message("안녕하세요!")
    assert result.mode == "solo"
    assert result.agents == []


def test_classify_simple_question_is_solo():
    """단순 질문 → solo."""
    result = classify_message("Python에서 리스트를 정렬하는 방법을 알려줘.")
    assert result.mode == "solo"


def test_classify_two_numbered_items_is_solo():
    """번호 목록 2개만 있으면 solo (팀 키워드 없을 때)."""
    result = classify_message("1. 조사 2. 분석")
    assert result.mode == "solo"


def test_classify_three_numbered_items_is_team():
    """번호 목록 3개 이상 → team."""
    result = classify_message("1. 시장 조사 2. 기술 설계 3. 마케팅 계획")
    assert result.mode == "team"
    assert len(result.agents) == 3


def test_classify_team_keyword_triggers_team():
    """'각각' 키워드만으로 team 감지."""
    result = classify_message("1. 시장 조사, 2. 마케팅을 각각 전문가가 작성해줘.")
    assert result.mode == "team"
    assert len(result.agents) == 2


def test_classify_startup_business_plan_is_team():
    """AI 스타트업 사업 계획서 요청 → team 4개 에이전트."""
    msg = (
        "팀프로젝트) AI 스타트업 사업 계획서를 작성해줘. "
        "1. 시장 조사, 2.기술 아키텍처 설계, 3. 투자 유치 전략, "
        "4. 마케팅 계획을 각각 전문가가 작성해줘."
    )
    result = classify_message(msg)
    assert result.mode == "team"
    assert len(result.agents) == 4
    roles = [a.role for a in result.agents]
    assert roles[0] == "Researcher"   # 시장 조사
    assert roles[1] == "Planner"      # 기술 아키텍처 설계
    assert roles[2] == "Planner"      # 투자 유치 전략
    assert roles[3] == "Writer"       # 마케팅 계획


def test_classify_five_items_capped():
    """6개 번호 항목 → 최대 5개 에이전트."""
    msg = "1. 조사 2. 설계 3. 구현 4. 테스트 5. 문서 6. 배포"
    result = classify_message(msg)
    assert result.mode == "team"
    assert len(result.agents) == 5
