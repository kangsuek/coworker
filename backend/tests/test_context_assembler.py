"""Context Assembler 테스트 (TDD RED)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.reader import ReaderAgent


@pytest.mark.asyncio
async def test_assemble_empty_results(db):
    """결과 없음 → None 반환."""
    agent = ReaderAgent(db)
    result = await agent._assemble_context({})
    assert result is None


@pytest.mark.asyncio
async def test_assemble_short_results(db):
    """3000자 미만 → 원문 그대로 포함."""
    agent = ReaderAgent(db)
    results = {"Researcher-A": "짧은 결과"}
    context = await agent._assemble_context(results)
    assert context is not None
    assert "Researcher-A" in context
    assert "짧은 결과" in context


@pytest.mark.asyncio
async def test_assemble_long_result_triggers_summary(db):
    """3000자 초과 → 요약 CLI 호출 확인."""
    agent = ReaderAgent(db)
    long_result = "A" * 3001
    results = {"Coder-A": long_result}

    with patch.object(agent, "_summarize_for_context", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = "요약된 결과"
        context = await agent._assemble_context(results)

    mock_summary.assert_called_once_with("Coder-A", long_result, run_id=None)
    assert "요약된 결과" in context


@pytest.mark.asyncio
async def test_assemble_format(db):
    """[Agent이름 결과]:\n내용 포맷 검증."""
    agent = ReaderAgent(db)
    results = {"Researcher-A": "리서치 내용"}
    context = await agent._assemble_context(results)
    assert "[Researcher-A 결과]:" in context
    assert "리서치 내용" in context


@pytest.mark.asyncio
async def test_second_agent_receives_first_result(db):
    """2번째 프롬프트에 1번째 결과 포함 확인."""
    agent = ReaderAgent(db)
    results = {
        "Researcher-A": "첫 번째 결과",
        "Coder-A": "두 번째 결과",
    }
    context = await agent._assemble_context(results)
    assert context is not None
    assert "Researcher-A" in context
    assert "첫 번째 결과" in context
    assert "Coder-A" in context
    assert "두 번째 결과" in context


@pytest.mark.asyncio
async def test_assemble_exactly_3000_chars(db):
    """정확히 3000자 → 요약 미호출."""
    agent = ReaderAgent(db)
    result = "A" * 3000
    results = {"Agent-A": result}
    with patch.object(agent, "_summarize_for_context", new_callable=AsyncMock) as mock_s:
        context = await agent._assemble_context(results)
    mock_s.assert_not_called()
    assert result in context


@pytest.mark.asyncio
async def test_assemble_exactly_3001_chars(db):
    """정확히 3001자 → 요약 호출 (경계값)."""
    agent = ReaderAgent(db)
    long_result = "A" * 3001
    results = {"Agent-A": long_result}
    with patch.object(agent, "_summarize_for_context", new_callable=AsyncMock) as mock_s:
        mock_s.return_value = "요약"
        context = await agent._assemble_context(results)
    mock_s.assert_called_once_with("Agent-A", long_result, run_id=None)
    assert "요약" in context
