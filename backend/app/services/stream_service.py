"""실시간 스트리밍 매니저 (SSE)."""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.queues: dict[str, list[asyncio.Queue]] = {}
        # 각 run_id의 마지막 이벤트를 저장 (늦은 구독자 대응)
        self.last_events: dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """특정 run_id의 실시간 업데이트를 수신할 큐를 생성하여 반환."""
        queue = asyncio.Queue()
        async with self.lock:
            if run_id not in self.queues:
                self.queues[run_id] = []
            self.queues[run_id].append(queue)
            
            # 마지막 이벤트를 즉시 전송 (있을 경우)
            if run_id in self.last_events:
                await queue.put(self.last_events[run_id])
                
        logger.debug("Subscribed to stream: run_id=%s, queue_id=%s", run_id, id(queue))
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        """구독 취소."""
        async with self.lock:
            if run_id in self.queues:
                if queue in self.queues[run_id]:
                    self.queues[run_id].remove(queue)
                if not self.queues[run_id]:
                    del self.queues[run_id]
                    # 구독자가 없어도 last_events는 일정 시간 유지할 수 있으나 여기서는 일단 함께 삭제
                    if run_id in self.last_events:
                        del self.last_events[run_id]
        logger.debug("Unsubscribed from stream: run_id=%s, queue_id=%s", run_id, id(queue))

    async def broadcast(self, run_id: str, data: Any):
        """특정 run_id를 구독 중인 모든 클라이언트에게 데이터 전송."""
        queues_to_send = []
        async with self.lock:
            # JSON 직렬화
            json_data = json.dumps(data, ensure_ascii=False)
            
            # 마지막 이벤트 업데이트 (type이 status인 경우 우선적으로 캐싱)
            if data.get("type") == "status":
                self.last_events[run_id] = json_data
                logger.debug("Cached last status for run_id=%s: %s", run_id, data.get("status"))

            if run_id in self.queues:
                # 큐 목록 복사 (락 범위 축소)
                queues_to_send = list(self.queues[run_id])
        
        if not queues_to_send:
            logger.debug("No subscribers for run_id=%s", run_id)
            return
            
        logger.debug("Broadcasting to %d subscribers for run_id=%s", len(queues_to_send), run_id)
        for queue in queues_to_send:
            await queue.put(json_data)

    def broadcast_sync(self, run_id: str, data: Any):
        """동기 컨텍스트(예: 스레드)에서 브로드캐스트 호출."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.broadcast(run_id, data))
                )
        except RuntimeError:
            pass

stream_manager = StreamManager()
