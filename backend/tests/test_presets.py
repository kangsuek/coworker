"""5개 프리셋 시스템 프롬프트 존재 검증 테스트 (TDD RED)."""

from app.agents.presets import coder, planner, researcher, reviewer, writer


def test_researcher_prompt_exists():
    assert hasattr(researcher, "SYSTEM_PROMPT")
    assert "리서치" in researcher.SYSTEM_PROMPT or "조사" in researcher.SYSTEM_PROMPT


def test_coder_prompt_exists():
    assert hasattr(coder, "SYSTEM_PROMPT")
    assert "코드" in coder.SYSTEM_PROMPT or "엔지니어" in coder.SYSTEM_PROMPT


def test_reviewer_prompt_exists():
    assert hasattr(reviewer, "SYSTEM_PROMPT")
    assert "리뷰" in reviewer.SYSTEM_PROMPT or "검토" in reviewer.SYSTEM_PROMPT


def test_writer_prompt_exists():
    assert hasattr(writer, "SYSTEM_PROMPT")
    assert "라이터" in writer.SYSTEM_PROMPT or "문서" in writer.SYSTEM_PROMPT


def test_planner_prompt_exists():
    assert hasattr(planner, "SYSTEM_PROMPT")
    assert "플래너" in planner.SYSTEM_PROMPT or "계획" in planner.SYSTEM_PROMPT


def test_all_presets_non_empty():
    for module in [researcher, coder, reviewer, writer, planner]:
        assert module.SYSTEM_PROMPT.strip() != ""
