"""세션 API 테스트 — Task 3-4."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.session_service import create_session, create_user_message


@pytest.mark.asyncio
async def test_list_sessions(client):
    """세션 2개 생성 → GET /api/sessions → 2개 반환."""
    await client.post("/api/sessions")
    await client.post("/api/sessions")
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_create_session(client):
    """POST /api/sessions → 201, id, created_at 포함."""
    response = await client.post("/api/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_session_detail(client, db):
    """세션+메시지 생성 → GET /api/sessions/{id} → messages 포함."""
    sess = await create_session(db)
    await create_user_message(db, sess.id, "user", "테스트 메시지")

    response = await client.get(f"/api/sessions/{sess.id}")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) >= 1


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    """없는 세션 → 404."""
    response = await client.get("/api/sessions/nonexistent-id")
    assert response.status_code == 404


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
async def test_list_sessions_pagination_offset(client):
    """?limit=2&offset=2 → 전체 목록 기준 3~4번째 세션 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        for i in range(4):
            await client.post("/api/chat", json={"message": f"테스트 {i}"})

    all_ids = [s["id"] for s in (await client.get("/api/sessions")).json()]
    paged_ids = [s["id"] for s in (await client.get("/api/sessions?limit=2&offset=2")).json()]

    assert len(paged_ids) == 2
    assert paged_ids == all_ids[2:4]
