"""Chat/Run API 테스트 — Task 3-2~3-3.

_run_reader_agent를 AsyncMock으로 패치해 CLI/DB 격리.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_post_chat_returns_run_id(client):
    """POST /api/chat → run_id, session_id 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        response = await client.post("/api/chat", json={"message": "안녕하세요"})
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "session_id" in data


@pytest.mark.asyncio
async def test_post_chat_creates_session_if_missing(client):
    """session_id 없이 POST → 세션 자동 생성."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        response = await client.post("/api/chat", json={"message": "테스트"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] is not None


@pytest.mark.asyncio
async def test_post_chat_invalid_llm_provider_returns_422(client):
    """지원하지 않는 llm_provider로 POST /api/chat → 422."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        response = await client.post(
            "/api/chat",
            json={"message": "테스트", "llm_provider": "unknown-provider"},
        )
    assert response.status_code == 422
    assert "Invalid llm_provider" in response.json()["detail"]


@pytest.mark.asyncio
async def test_post_chat_persists_llm_settings(client):
    """POST /api/chat 시 llm_provider, llm_model 전달 → 세션 조회 시 해당 값 반영."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        response = await client.post(
            "/api/chat",
            json={
                "message": "모델 설정 테스트",
                "llm_provider": "claude-cli",
                "llm_model": "claude-3-5-sonnet",
            },
        )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    get_resp = await client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["llm_provider"] == "claude-cli"
    assert data["llm_model"] == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_post_chat_returns_fast(client):
    """POST → 응답 시간 < 1.0초 (백그라운드 처리 확인)."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        start = time.monotonic()
        response = await client.post("/api/chat", json={"message": "빠른 응답 테스트"})
        elapsed = time.monotonic() - start
    assert response.status_code == 200
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_get_run_status(client):
    """POST → run_id → GET /api/runs/{run_id} → status 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        post_response = await client.post("/api/chat", json={"message": "상태 테스트"})
    run_id = post_response.json()["run_id"]

    get_response = await client.get(f"/api/runs/{run_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_get_run_status_not_found(client):
    """GET /api/runs/invalid → 404."""
    response = await client.get("/api/runs/nonexistent-run-id")
    assert response.status_code == 404


# --- Task 5-6: GET /api/runs/{run_id}/agent-messages ---


@pytest.mark.asyncio
async def test_get_agent_messages(client, db):
    """agent_messages 조회 반환."""
    from app.services.session_service import (
        create_agent_message,
        create_run,
        create_session,
        create_user_message,
    )

    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)
    await create_agent_message(db, sess.id, run.id, "Researcher-A", "Researcher")

    resp = await client.get(f"/api/runs/{run.id}/agent-messages")
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["sender"] == "Researcher-A"


@pytest.mark.asyncio
async def test_get_agent_messages_empty(client, db):
    """메시지 없음 → 빈 배열."""
    from app.services.session_service import create_run, create_session, create_user_message

    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)

    resp = await client.get(f"/api/runs/{run.id}/agent-messages")
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


@pytest.mark.asyncio
async def test_get_agent_messages_includes_working(client, db):
    """working 상태 중간 출력 포함 확인."""
    from app.services.session_service import (
        create_agent_message,
        create_run,
        create_session,
        create_user_message,
        update_agent_message_content,
    )

    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)
    msg = await create_agent_message(db, sess.id, run.id, "Coder-A", "Coder")
    await update_agent_message_content(db, msg.id, "중간 출력 내용")

    resp = await client.get(f"/api/runs/{run.id}/agent-messages")
    data = resp.json()
    assert data["messages"][0]["content"] == "중간 출력 내용"
    assert data["messages"][0]["status"] == "working"
