"""Reader Agent 테스트 — Task 3-1.

call_claude_streaming을 완전히 mock해 CLI 호출 없이 테스트.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.reader import ReaderAgent
from app.models.db import Run
from app.services.session_service import create_run, create_session, create_user_message


@pytest.mark.asyncio
async def test_process_message_logs_error_on_exception(db):
    """CLI 에러 발생 시 logger.exception 호출 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "오류 테스트")
    run = await create_run(db, sess.id, msg.id)

    with (
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
        patch("app.agents.reader.logger") as mock_logger,
    ):
        mock_cli.side_effect = RuntimeError("CLI 오류")
        await ReaderAgent(db).process_message(sess.id, "오류 테스트", run.id)

    mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_classify_returns_solo(db):
    """call_claude_streaming mock → solo 분류 결과 반환."""
    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = '{"mode":"solo","reason":"간단한 질문","agents":[]}'
        agent = ReaderAgent(db)
        result = await agent._classify("안녕하세요")
    assert result.mode == "solo"


@pytest.mark.asyncio
async def test_classify_returns_team(db):
    """call_claude_streaming mock → team 분류 결과 반환."""
    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = (
            '{"mode":"team","reason":"복잡한 작업",'
            '"agents":[{"role":"Researcher","task":"조사"}]}'
        )
        agent = ReaderAgent(db)
        result = await agent._classify("복잡한 프로젝트를 개발해주세요")
    assert result.mode == "team"
    assert len(result.agents) == 1


@pytest.mark.asyncio
async def test_solo_respond_returns_text(db):
    """call_claude_streaming mock → 응답 텍스트 반환."""
    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = "응답 텍스트"
        agent = ReaderAgent(db)
        result = await agent._solo_respond("질문입니다")
    assert result == "응답 텍스트"


@pytest.mark.asyncio
async def test_process_message_solo_flow(db):
    """Solo 흐름: run status 'done', response 저장, mode='solo' 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "안녕")
    run = await create_run(db, sess.id, msg.id)

    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.side_effect = [
            '{"mode":"solo","reason":"간단","agents":[]}',
            "안녕하세요!",
        ]
        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "안녕", run.id)

    updated_run = await db.get(Run, run.id)
    assert updated_run.status == "done"
    assert updated_run.response == "안녕하세요!"
    assert updated_run.mode == "solo"


@pytest.mark.asyncio
async def test_process_message_error_handling(db):
    """CLI 오류 → run status='error'."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "오류 테스트")
    run = await create_run(db, sess.id, msg.id)

    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.side_effect = RuntimeError("CLI 오류")
        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "오류 테스트", run.id)

    updated_run = await db.get(Run, run.id)
    assert updated_run.status == "error"
