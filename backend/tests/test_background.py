"""3-5. 백그라운드 실행 관리 테스트.

_run_reader_agent가 run status를 올바르게 업데이트하고,
ReaderAgent가 execute_with_lock을 통해 Lock을 획득함을 검증.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.chat import _run_reader_agent
from app.services.session_service import create_run, create_session, create_user_message


def _make_session_cm(db):
    """async_session()이 반환하는 컨텍스트 매니저 mock."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.mark.asyncio
async def test_background_task_updates_run_status(db):
    """_run_reader_agent 실행 시 run status queued → done 으로 변화."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "안녕")
    run = await create_run(db, sess.id, msg.id)

    with (
        patch("app.routers.chat.async_session", return_value=_make_session_cm(db)),
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
    ):
        mock_cli.side_effect = [
            '{"mode":"solo","reason":"단순","agents":[]}',
            "완료 응답",
        ]
        await _run_reader_agent(sess.id, "안녕", run.id)

    await db.refresh(run)
    assert run.status == "done"
    assert run.response == "완료 응답"


@pytest.mark.asyncio
async def test_background_task_acquires_lock(db):
    """ReaderAgent 실행 시 execute_with_lock이 최소 2회 호출됨을 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "테스트")
    run = await create_run(db, sess.id, msg.id)

    lock_calls: list[bool] = []

    async def mock_execute_with_lock(coro):
        lock_calls.append(True)
        return await coro

    with (
        patch("app.agents.reader.execute_with_lock", side_effect=mock_execute_with_lock),
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
    ):
        mock_cli.side_effect = [
            '{"mode":"solo","reason":"단순","agents":[]}',
            "응답",
        ]
        from app.agents.reader import ReaderAgent

        await ReaderAgent(db).process_message(sess.id, "테스트", run.id)

    # 분류 1회 + Solo 응답 1회 = 2회
    assert len(lock_calls) >= 2
