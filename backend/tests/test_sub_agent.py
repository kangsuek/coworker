"""Sub-Agent 기반 클래스 테스트 (TDD RED)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.sub_agent import SubAgent


@pytest.mark.asyncio
async def test_sub_agent_execute():
    """CLI mock → 태스크 결과 반환."""
    agent = SubAgent(name="Researcher-A", role_preset="Researcher", system_prompt="리서치 전문가")

    with patch("app.agents.sub_agent.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = "리서치 결과입니다."
        result = await agent.execute(task="AI 트렌드 조사", context=None, on_line=None)

    assert result == "리서치 결과입니다."
    mock_cli.assert_called_once()


@pytest.mark.asyncio
async def test_sub_agent_build_prompt_without_context():
    """context 없음 → task만 포함."""
    agent = SubAgent(name="Coder-A", role_preset="Coder", system_prompt="코더")
    prompt = agent._build_prompt(task="함수 작성", context=None)
    assert "함수 작성" in prompt
    assert "이전 작업 결과" not in prompt


@pytest.mark.asyncio
async def test_sub_agent_build_prompt_with_context():
    """context 존재 → 이전 결과 주입."""
    agent = SubAgent(name="Coder-A", role_preset="Coder", system_prompt="코더")
    prompt = agent._build_prompt(task="함수 작성", context="이전 리서치 결과")
    assert "함수 작성" in prompt
    assert "이전 작업 결과" in prompt
    assert "이전 리서치 결과" in prompt


@pytest.mark.asyncio
async def test_sub_agent_calls_on_line():
    """실행 중 on_line 콜백 호출 확인."""
    agent = SubAgent(name="Writer-A", role_preset="Writer", system_prompt="라이터")
    received_lines: list[str] = []

    def on_line(line: str) -> None:
        received_lines.append(line)

    async def fake_call(system_prompt, user_message, on_line=None, **kwargs):
        if on_line:
            on_line("첫 번째 줄\n")
            on_line("두 번째 줄\n")
        return "첫 번째 줄\n두 번째 줄\n"

    with patch("app.agents.sub_agent.call_claude_streaming", side_effect=fake_call):
        await agent.execute(task="문서 작성", context=None, on_line=on_line)

    assert len(received_lines) == 2
    assert "첫 번째 줄" in received_lines[0]
