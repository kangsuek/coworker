"""세션 API 테스트 — Task 3-4."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.db import Run, UserMessage
from app.services.session_service import (
    create_agent_message,
    create_run,
    create_session,
    create_user_message,
)


@pytest.mark.asyncio
async def test_list_sessions(client):
    """세션 2개 생성 → GET /api/sessions → 2개 반환, 각 항목에 llm_provider/llm_model 포함."""
    await client.post("/api/sessions")
    await client.post("/api/sessions")
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for s in data:
        assert "llm_provider" in s
        assert "llm_model" in s
        assert s["llm_provider"] == "claude-cli"


@pytest.mark.asyncio
async def test_create_session(client):
    """POST /api/sessions → 201, id, created_at, llm_provider, llm_model 포함."""
    response = await client.post("/api/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "llm_provider" in data
    assert data["llm_provider"] == "claude-cli"
    assert "llm_model" in data
    assert data["llm_model"] is None


@pytest.mark.asyncio
async def test_get_session_detail(client, db):
    """세션+메시지 생성 → GET /api/sessions/{id} → messages, llm_provider, llm_model 포함."""
    sess = await create_session(db)
    await create_user_message(db, sess.id, "user", "테스트 메시지")

    response = await client.get(f"/api/sessions/{sess.id}")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) >= 1
    assert "llm_provider" in data
    assert "llm_model" in data
    assert data["llm_provider"] == "claude-cli"
    assert data["llm_model"] is None


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    """없는 세션 → 404."""
    response = await client.get("/api/sessions/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client, db):
    """세션 생성 → DELETE /api/sessions/{id} → 204, 목록에서 제거."""
    sess = await create_session(db)
    resp = await client.delete(f"/api/sessions/{sess.id}")
    assert resp.status_code == 204
    list_resp = await client.get("/api/sessions")
    ids = [s["id"] for s in list_resp.json()]
    assert sess.id not in ids


@pytest.mark.asyncio
async def test_delete_session_not_found(client):
    """없는 세션 삭제 → 404."""
    response = await client.delete("/api/sessions/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_cascades_children(client, db):
    """세션 삭제 시 runs, agent_messages, user_messages도 모두 삭제."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "테스트")
    run = await create_run(db, sess.id, user_msg.id)
    await create_agent_message(db, sess.id, run.id, "Researcher-1", "Researcher")

    resp = await client.delete(f"/api/sessions/{sess.id}")
    assert resp.status_code == 204

    # 자식 레코드가 모두 삭제됐는지 확인
    remaining_runs = (
        await db.execute(select(Run).where(Run.session_id == sess.id))
    ).scalars().all()
    remaining_msgs = (
        await db.execute(select(UserMessage).where(UserMessage.session_id == sess.id))
    ).scalars().all()
    assert remaining_runs == []
    assert remaining_msgs == []


@pytest.mark.asyncio
async def test_delete_session_with_active_run_calls_cancel(client, db):
    """실행 중인 Run이 있는 세션 삭제 시 cancel_current가 호출됨."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "테스트")
    run = await create_run(db, sess.id, user_msg.id)
    # Run을 활성 상태로 설정
    from app.services.session_service import update_run_status
    await update_run_status(db, run.id, "working")

    with patch("app.routers.sessions.cancel_current", new_callable=AsyncMock) as mock_cancel:
        resp = await client.delete(f"/api/sessions/{sess.id}")
        assert resp.status_code == 204
        mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_delete_session_without_active_run_skips_cancel(client, db):
    """실행 중인 Run이 없는 세션 삭제 시 cancel_current를 호출하지 않음."""
    sess = await create_session(db)

    with patch("app.routers.sessions.cancel_current", new_callable=AsyncMock) as mock_cancel:
        resp = await client.delete(f"/api/sessions/{sess.id}")
        assert resp.status_code == 204
        mock_cancel.assert_not_called()


@pytest.mark.asyncio
async def test_list_sessions_pagination_limit(client):
    """?limit=2 → 최신 2개만 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        for i in range(4):
            await client.post("/api/chat", json={"message": f"테스트 {i}"})

    resp = await client.get("/api/sessions?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_session_detail_returns_llm_settings(client, db):
    """커스텀 llm_provider/llm_model으로 생성한 세션 → GET 상세 시 해당 값 반환."""
    sess = await create_session(db, llm_provider="claude-cli", llm_model="claude-3-5-sonnet")
    response = await client.get(f"/api/sessions/{sess.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["llm_provider"] == "claude-cli"
    assert data["llm_model"] == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_list_sessions_pagination_offset(client):
    """?limit=2&offset=2 → 전체 목록 기준 3~4번째 세션 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        for i in range(4):
            await client.post("/api/chat", json={"message": f"테스트 {i}"})

    all_ids = [s["id"] for s in (await client.get("/api/sessions")).json()]
    paged_ids = [s["id"] for s in (await client.get("/api/sessions?limit=2&offset=2")).json()]

    assert len(paged_ids) == 2
    assert paged_ids == all_ids[2:4]
