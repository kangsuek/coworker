"""SSE 스트리밍 정밀 통합 테스트."""

import asyncio
import json
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.session_service import create_run, create_session, create_user_message
from app.services.stream_service import stream_manager

@pytest.mark.asyncio
async def test_sse_comprehensive_flow(db):
    """모든 이벤트 타입에 대한 스트리밍 흐름을 검증."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "정밀 테스트")
    run = await create_run(db, session.id, user_msg.id)

    # 1. 시뮬레이션할 이벤트 목록
    events_to_send = [
        {"type": "status", "status": "thinking", "run_id": run.id},
        {"type": "agent_message_created", "run_id": run.id, "agent_message": {"id": "m1", "sender": "Res-1"}},
        {"type": "content", "run_id": run.id, "agent": "Res-1", "content": "Analyzing..."},
        {"type": "agent_status_changed", "run_id": "m1", "status": "done"},
        {"type": "status", "status": "done", "run_id": run.id}
    ]

    async def producer():
        await asyncio.sleep(0.2) # 클라이언트 접속 대기
        for ev in events_to_send:
            await stream_manager.broadcast(run.id, ev)
            await asyncio.sleep(0.05)

    captured_data = []
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        prod_task = asyncio.create_task(producer())
        
        try:
            async with ac.stream("GET", f"/api/runs/{run.id}/stream", timeout=5.0) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        captured_data.append(data)
                        # 마지막 이벤트까지 받으면 종료
                        if data.get("status") == "done" and data.get("type") == "status":
                            break
        finally:
            if not prod_task.done():
                prod_task.cancel()

    # 2. 검증: 보낸 이벤트 수와 받은 이벤트 수가 일치하는지 확인
    assert len(captured_data) == len(events_to_send)
    assert captured_data[0]["status"] == "thinking"
    assert captured_data[2]["content"] == "Analyzing..."
    assert captured_data[4]["status"] == "done"

@pytest.mark.asyncio
async def test_sse_multiple_subscribers(db):
    """하나의 Run에 대해 여러 클라이언트가 동시에 스트리밍을 수신하는지 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "멀티 구독 테스트")
    run = await create_run(db, session.id, user_msg.id)

    async def consumer(name):
        results = []
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            try:
                async with ac.stream("GET", f"/api/runs/{run.id}/stream", timeout=3.0) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            results.append(data)
                            if data.get("type") == "status" and data.get("status") == "done":
                                break
            except Exception:
                pass
        return results

    # 두 클라이언트가 동시에 구독 시작
    c1_task = asyncio.create_task(consumer("Client-1"))
    c2_task = asyncio.create_task(consumer("Client-2"))
    
    await asyncio.sleep(0.2)
    
    # 데이터 브로드캐스트
    test_event = {"type": "content", "content": "Broadcast Test"}
    done_event = {"type": "status", "status": "done"}
    await stream_manager.broadcast(run.id, test_event)
    await stream_manager.broadcast(run.id, done_event)
    
    res1 = await c1_task
    res2 = await c2_task
    
    assert len(res1) == 2
    assert len(res2) == 2
    assert res1[0]["content"] == "Broadcast Test"
    assert res2[0]["content"] == "Broadcast Test"

@pytest.mark.asyncio
async def test_sse_cleanup_on_disconnect(db):
    """클라이언트 연결 종료 시 StreamManager에서 큐가 정리되는지 확인."""
    session = await create_session(db)
    user_msg = await create_user_message(db, session.id, "user", "정리 테스트")
    run = await create_run(db, session.id, user_msg.id)

    # 현재 구독 중인 큐 개수 확인
    initial_queues = len(stream_manager.queues.get(run.id, []))
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 스트림 시작
        async with ac.stream("GET", f"/api/runs/{run.id}/stream") as resp:
            await asyncio.sleep(0.1)
            # 구독자가 1명 추가되었어야 함
            assert len(stream_manager.queues.get(run.id, [])) == initial_queues + 1
            # 여기서 강제로 연결 종료 (with 블록 탈출)
    
    # 구독 해제 로직이 비동기로 동작하므로 잠시 대기
    await asyncio.sleep(0.2)
    
    # 구독자가 다시 0명이 되어야 함 (또는 run_id 키 자체가 삭제됨)
    final_queues = len(stream_manager.queues.get(run.id, []))
    assert final_queues == initial_queues
