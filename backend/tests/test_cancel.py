"""취소 기능 테스트 (TDD RED)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.session_service import (
    create_run,
    create_session,
    create_user_message,
    update_run_status,
)


@pytest.mark.asyncio
async def test_cancel_solo_run(client, db):
    """Solo 실행 중 취소 → cancelled 상태 반환."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "작업")
    run = await create_run(db, session.id, user_msg.id)
    await update_run_status(db, run.id, "solo")

    with patch("app.routers.chat.cancel_current", new_callable=AsyncMock):
        resp = await client.post(f"/api/runs/{run.id}/cancel")

    assert resp.status_code == 200
    run_resp = await client.get(f"/api/runs/{run.id}")
    assert run_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_invalid_status(client, db):
    """done 상태에서 취소 → 무시 (200 반환, 상태 변경 없음)."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "완료된 작업")
    run = await create_run(db, session.id, user_msg.id)
    await update_run_status(db, run.id, "done", response="완료")

    with patch("app.routers.chat.cancel_current", new_callable=AsyncMock):
        resp = await client.post(f"/api/runs/{run.id}/cancel")

    assert resp.status_code == 200
    run_resp = await client.get(f"/api/runs/{run.id}")
    assert run_resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_cancel_kills_process_group(client, db):
    """취소 가능 상태에서 cancel_current() 호출 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "작업")
    run = await create_run(db, session.id, user_msg.id)
    await update_run_status(db, run.id, "working")

    with patch("app.routers.chat.cancel_current", new_callable=AsyncMock) as mock_cancel:
        await client.post(f"/api/runs/{run.id}/cancel")

    mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_team_run(client, db):
    """Team 실행 중 취소 → cancelled, 완료된 run 정보 보존."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "팀 작업")
    run = await create_run(db, session.id, user_msg.id)
    await update_run_status(db, run.id, "working", mode="team")

    with patch("app.routers.chat.cancel_current", new_callable=AsyncMock):
        resp = await client.post(f"/api/runs/{run.id}/cancel")

    assert resp.status_code == 200
    run_resp = await client.get(f"/api/runs/{run.id}")
    assert run_resp.json()["status"] == "cancelled"
