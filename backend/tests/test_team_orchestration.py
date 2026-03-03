"""Team 오케스트레이션 상태 흐름 테스트 (TDD RED)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.reader import ReaderAgent
from app.models.schemas import AgentPlan, ClassificationResult
from app.services.session_service import create_run, create_session, create_user_message


@pytest.mark.asyncio
async def test_team_execute_status_flow(db):
    """상태 변화: delegating → working → integrating → done."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "복잡한 팀 작업")
    run = await create_run(db, session.id, user_msg.id)

    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[
            AgentPlan(role="Researcher", task="리서치"),
            AgentPlan(role="Coder", task="코딩"),
        ],
        user_status_message=None,
    )

    statuses: list[str] = []

    async def fake_update_run(db, run_id, status, **fields):
        statuses.append(status)
        from app.services.session_service import update_run_status as real_update
        return await real_update(db, run_id, status, **fields)

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    with (
        patch("app.agents.reader.update_run_status", side_effect=fake_update_run),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch.object(agent, "_integrate_results", new_callable=AsyncMock, return_value="통합 결과"),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            return_value="결과",
        ),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch("app.agents.reader.update_agent_message_status", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-agent-msg-id"
        mock_create_am.return_value = mock_am
        await agent._team_execute(classification, "복잡한 팀 작업", session.id, run.id)

    assert "delegating" in statuses
    assert "working" in statuses
    assert "integrating" in statuses
    assert "done" in statuses


@pytest.mark.asyncio
async def test_team_execute_runs_agents_sequentially(db):
    """2개 Agent 순차 실행 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "팀 작업")
    run = await create_run(db, session.id, user_msg.id)

    call_order: list[str] = []
    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[
            AgentPlan(role="Researcher", task="리서치"),
            AgentPlan(role="Coder", task="코딩"),
        ],
        user_status_message=None,
    )

    async def fake_execute(task, context, on_line, model=""):
        call_order.append(task)
        return f"{task} 결과"

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    with (
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch.object(agent, "_integrate_results", new_callable=AsyncMock, return_value="통합"),
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            return_value="",
        ),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch("app.agents.reader.update_agent_message_status", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-id"
        mock_create_am.return_value = mock_am

        with patch("app.agents.sub_agent.SubAgent.execute", side_effect=fake_execute):
            await agent._team_execute(classification, "팀 작업", session.id, run.id)

    # full_task는 "[전체 프로젝트 요청]...\n[당신의 담당 태스크]\n{task}" 포맷으로 전달됨
    assert len(call_order) == 2
    assert "리서치" in call_order[0]
    assert "코딩" in call_order[1]


@pytest.mark.asyncio
async def test_team_execute_integrates_results(db):
    """통합 CLI 호출 + 최종 응답 저장."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "통합 요청")
    run = await create_run(db, session.id, user_msg.id)

    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[AgentPlan(role="Researcher", task="리서치")],
        user_status_message=None,
    )

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    saved_messages: list[str] = []

    async def fake_create_user_message(db, session_id, role, content, mode=None):
        saved_messages.append(content)

    with (
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", side_effect=fake_create_user_message),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch.object(
            agent, "_integrate_results", new_callable=AsyncMock, return_value="최종 통합 응답"
        ),
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            return_value="결과",
        ),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch("app.agents.reader.update_agent_message_status", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-id"
        mock_create_am.return_value = mock_am
        await agent._team_execute(classification, "통합 요청", session.id, run.id)

    assert "최종 통합 응답" in saved_messages


@pytest.mark.asyncio
async def test_team_execute_records_agent_messages(db):
    """agent_messages DB 기록 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "작업")
    run = await create_run(db, session.id, user_msg.id)

    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[
            AgentPlan(role="Researcher", task="리서치"),
            AgentPlan(role="Writer", task="문서 작성"),
        ],
        user_status_message=None,
    )

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    with (
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch.object(agent, "_integrate_results", new_callable=AsyncMock, return_value="통합"),
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            return_value="",
        ),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch(
            "app.agents.reader.update_agent_message_status", new_callable=AsyncMock
        ) as mock_update_status,
    ):
        mock_am = MagicMock()
        mock_am.id = "test-id"
        mock_create_am.return_value = mock_am
        await agent._team_execute(classification, "작업", session.id, run.id)

    # Agent 2개이므로 create_agent_message 2번 호출
    assert mock_create_am.call_count == 2
    # 각 Agent 완료 시 status "done" 업데이트
    done_calls = [c for c in mock_update_status.call_args_list if "done" in c.args]
    assert len(done_calls) == 2


@pytest.mark.asyncio
async def test_team_execute_sub_agent_exception_sets_error_status(db):
    """Sub-Agent 실행 중 Exception → agent_message status 'error' + 예외 전파."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "작업")
    run = await create_run(db, session.id, user_msg.id)

    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[AgentPlan(role="Researcher", task="리서치")],
        user_status_message=None,
    )

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    with (
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch(
            "app.agents.reader.update_agent_message_status", new_callable=AsyncMock
        ) as mock_update_status,
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            side_effect=RuntimeError("CLI 실패"),
        ),
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-id"
        mock_create_am.return_value = mock_am

        with pytest.raises(RuntimeError, match="CLI 실패"):
            await agent._team_execute(classification, "작업", session.id, run.id)

    error_calls = [c for c in mock_update_status.call_args_list if "error" in c.args]
    assert len(error_calls) == 1


@pytest.mark.asyncio
async def test_team_execute_integrate_results_failure_propagates(db):
    """_integrate_results CLI 실패 → 예외 전파 (done 미전환)."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "통합 실패")
    run = await create_run(db, session.id, user_msg.id)

    classification = ClassificationResult(
        mode="team",
        reason="복잡함",
        agents=[AgentPlan(role="Researcher", task="리서치")],
        user_status_message=None,
    )

    statuses: list[str] = []

    async def fake_update_run(db, run_id, status, **fields):
        statuses.append(status)
        from app.services.session_service import update_run_status as real_update

        return await real_update(db, run_id, status, **fields)

    agent = ReaderAgent(db)
    from app.services.llm import get_provider
    agent.llm_provider = get_provider("claude-cli")
    agent.session_model = None
    with (
        patch("app.agents.reader.update_run_status", side_effect=fake_update_run),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch.object(agent, "_assemble_context", new_callable=AsyncMock, return_value=None),
        patch.object(
            agent,
            "_integrate_results",
            new_callable=AsyncMock,
            side_effect=RuntimeError("통합 CLI 실패"),
        ),
        patch(
            "app.services.llm.claude_cli.ClaudeCliProvider.stream_generate",
            new_callable=AsyncMock,            return_value="결과",
        ),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch("app.agents.reader.update_agent_message_status", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-id"
        mock_create_am.return_value = mock_am

        with pytest.raises(RuntimeError, match="통합 CLI 실패"):
            await agent._team_execute(classification, "통합 실패", session.id, run.id)

    assert "done" not in statuses
