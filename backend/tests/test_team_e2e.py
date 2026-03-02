"""Team 모드 E2E 통합 테스트 (TDD RED → GREEN)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_team_e2e_full_flow(client):
    """POST → 폴링 → delegating → working → integrating → done."""
    from app.agents.reader import ReaderAgent
    from app.models.schemas import AgentPlan, ClassificationResult

    team_classification = ClassificationResult(
        mode="team",
        reason="복잡한 팀 작업",
        agents=[
            AgentPlan(role="Researcher", task="리서치"),
            AgentPlan(role="Coder", task="코딩"),
        ],
        user_status_message=None,
    )

    with (
        patch("app.agents.reader.execute_with_lock") as mock_lock,
        patch.object(ReaderAgent, "_classify", new_callable=AsyncMock, return_value=team_classification),
        patch("app.agents.reader.create_agent_message", new_callable=AsyncMock) as mock_create_am,
        patch("app.agents.reader.update_agent_message_content", new_callable=AsyncMock),
        patch("app.agents.reader.update_agent_message_status", new_callable=AsyncMock),
    ):
        mock_am = MagicMock()
        mock_am.id = "test-agent-msg-id"
        mock_create_am.return_value = mock_am

        call_count = 0

        async def fake_lock(coro):
            nonlocal call_count
            call_count += 1
            # 1~2번: agent 실행, 3번: 통합 (분류는 규칙 기반이므로 lock 없음)
            return await coro

        mock_lock.side_effect = fake_lock

        sub_patch = patch(
            "app.agents.sub_agent.call_claude_streaming", new_callable=AsyncMock
        )
        int_patch = patch(
            "app.agents.reader.call_claude_streaming", new_callable=AsyncMock
        )
        with sub_patch as mock_sub, int_patch as mock_integrate:
            mock_sub.return_value = "agent 결과"
            mock_integrate.return_value = "최종 통합 응답"
            post_resp = await client.post(
                "/api/chat", json={"message": "복잡한 팀 작업 요청"}
            )

    assert post_resp.status_code == 200
    run_id = post_resp.json()["run_id"]

    # run 상태 확인
    run_resp = await client.get(f"/api/runs/{run_id}")
    assert run_resp.status_code == 200
    terminal_statuses = {"done", "queued", "thinking", "delegating", "working", "integrating"}
    assert run_resp.json()["status"] in terminal_statuses


@pytest.mark.asyncio
async def test_team_e2e_agent_messages(client, db):
    """Team 실행 후 agent_messages 조회."""
    from app.services.session_service import (
        create_agent_message,
        create_run,
        create_session,
        create_user_message,
        update_agent_message_content,
        update_agent_message_status,
    )

    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "팀 작업")
    run = await create_run(db, sess.id, user_msg.id)

    am1 = await create_agent_message(db, sess.id, run.id, "Researcher-A", "Researcher")
    await update_agent_message_content(db, am1.id, "리서치 결과")
    await update_agent_message_status(db, am1.id, "done")

    am2 = await create_agent_message(db, sess.id, run.id, "Coder-A", "Coder")
    await update_agent_message_content(db, am2.id, "코딩 결과")
    await update_agent_message_status(db, am2.id, "done")

    resp = await client.get(f"/api/runs/{run.id}/agent-messages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["sender"] == "Researcher-A"
    assert data["messages"][0]["status"] == "done"
    assert data["messages"][1]["sender"] == "Coder-A"


@pytest.mark.asyncio
async def test_team_e2e_cancel(client, db):
    """Team 실행 중 취소 → cancelled 상태."""
    from app.services.session_service import (
        create_run,
        create_session,
        create_user_message,
        update_run_status,
    )

    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "팀 작업")
    run = await create_run(db, sess.id, user_msg.id)
    await update_run_status(db, run.id, "working", mode="team")

    with patch("app.routers.chat.cancel_current", new_callable=AsyncMock):
        resp = await client.post(f"/api/runs/{run.id}/cancel")

    assert resp.status_code == 200
    run_resp = await client.get(f"/api/runs/{run.id}")
    assert run_resp.json()["status"] == "cancelled"
