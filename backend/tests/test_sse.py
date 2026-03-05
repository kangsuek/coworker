"""SSE 스트리밍 엔드포인트 테스트 (Task 2.3 통합 테스트)."""

import asyncio
import json
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.session_service import create_run, create_session, create_user_message
from app.services.stream_service import stream_manager


@pytest.mark.asyncio
@pytest.mark.skip(reason="httpx ASGI stream은 스트리밍 응답 시 context manager 반환 전에 블로킹됨; E2E 또는 실제 클라이언트로 검증")
async def test_run_stream_endpoint_returns_sse_headers(db):
    """GET /api/runs/{run_id}/stream 이 200과 text/event-stream 헤더 및 연결 이벤트를 반환하는지 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "스트림 테스트")
    run = await create_run(db, session.id, user_msg.id)
    run_id = str(run.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with ac.stream("GET", f"/api/runs/{run_id}/stream", timeout=3.0) as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type.lower()
            # 연결 직후 전송되는 첫 이벤트 수신 (한 줄만 읽고 종료)
            first_line = None
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    first_line = line[6:]
                    break
            assert first_line is not None, "스트림에서 첫 data 이벤트를 수신하지 못함"
            data = json.loads(first_line)
            assert data.get("type") == "connected" and data.get("run_id") == run_id


@pytest.mark.asyncio
async def test_stream_manager_delivers_events():
    """stream_manager 구독·브로드캐스트 시 실시간으로 이벤트가 전달되는지 확인 (SSE 백엔드 동작 검증)."""
    run_id = "test-run-sse-integration"
    queue = await stream_manager.subscribe(run_id)

    async def broadcast_events():
        await asyncio.sleep(0.05)
        await stream_manager.broadcast(run_id, {"type": "content", "agent": "A", "content": "Hello"})
        await asyncio.sleep(0.02)
        await stream_manager.broadcast(run_id, {"type": "content", "agent": "A", "content": "World"})

    sender = asyncio.create_task(broadcast_events())
    try:
        first = await asyncio.wait_for(queue.get(), timeout=1.0)
        second = await asyncio.wait_for(queue.get(), timeout=1.0)
    finally:
        if not sender.done():
            sender.cancel()
        await stream_manager.unsubscribe(run_id, queue)

    data1 = json.loads(first)
    data2 = json.loads(second)
    assert data1.get("content") == "Hello"
    assert data2.get("content") == "World"
