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
