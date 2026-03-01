"""JSON 파싱 폴백 체인 테스트 — Task 2-3.

테스트 대상: parse_classification()
- 1단계: 정상 JSON -> Pydantic 검증
- 2단계: 텍스트+JSON 혼합 -> 정규식 추출
- 3단계: 파싱 불가 -> Solo 폴백
"""

from app.services.classification import parse_classification


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
