"""실시간 스트리밍 매니저 (SSE)."""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.queues: dict[str, list[asyncio.Queue]] = {}
        # run_id별 캐시: status 이벤트 + agent 생성/내용 이벤트 (늦은 구독자 재전송용)
        self.last_status: dict[str, str] = {}          # run_id → 마지막 status 이벤트 JSON
        self.agent_created: dict[str, list[str]] = {}  # run_id → agent_message_created 이벤트 목록
        self.last_content: dict[str, str] = {}         # "{run_id}:{agent}" → 마지막 content 이벤트 JSON
        self.lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """특정 run_id의 실시간 업데이트를 수신할 큐를 생성하여 반환.

        늦은 구독자(재연결 클라이언트)를 위해 캐시된 이벤트를 즉시 전송:
        1. agent_message_created 이벤트 (에이전트 목록 복원)
        2. 각 에이전트의 마지막 content 이벤트 (진행 중 내용 복원)
        3. 마지막 status 이벤트 (현재 실행 상태 복원)
        """
        queue = asyncio.Queue()
        async with self.lock:
            if run_id not in self.queues:
                self.queues[run_id] = []
            self.queues[run_id].append(queue)

            # 에이전트 생성 이벤트 재전송 (순서 보장)
            for event_json in self.agent_created.get(run_id, []):
                await queue.put(event_json)
            # 에이전트별 마지막 content 재전송
            for key, event_json in self.last_content.items():
                if key.startswith(f"{run_id}:"):
                    await queue.put(event_json)
            # 마지막 status 재전송
            if run_id in self.last_status:
                await queue.put(self.last_status[run_id])

        logger.debug("Subscribed to stream: run_id=%s, queue_id=%s", run_id, id(queue))
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        """구독 취소. 구독자가 0명이 되면 캐시 정리."""
        async with self.lock:
            if run_id in self.queues:
                if queue in self.queues[run_id]:
                    self.queues[run_id].remove(queue)
                if not self.queues[run_id]:
                    del self.queues[run_id]
                    # 구독자가 모두 떠나면 캐시 정리
                    self.last_status.pop(run_id, None)
                    self.agent_created.pop(run_id, None)
                    # content 캐시 중 해당 run_id 항목 정리
                    keys_to_del = [k for k in self.last_content if k.startswith(f"{run_id}:")]
                    for k in keys_to_del:
                        del self.last_content[k]
        logger.debug("Unsubscribed from stream: run_id=%s, queue_id=%s", run_id, id(queue))

    _TERMINAL_STATUSES = {"done", "error", "cancelled"}
    _CACHE_TTL = 30.0  # terminal 상태 후 캐시 유지 시간 (초)

    async def _schedule_cache_cleanup(self, run_id: str):
        """terminal 상태 브로드캐스트 후 TTL 만료 시 캐시 자동 정리."""
        await asyncio.sleep(self._CACHE_TTL)
        async with self.lock:
            # 아직 구독자가 있으면 unsubscribe 시 정리되므로 건너뜀
            if run_id in self.queues:
                return
            self.last_status.pop(run_id, None)
            self.agent_created.pop(run_id, None)
            keys_to_del = [k for k in self.last_content if k.startswith(f"{run_id}:")]
            for k in keys_to_del:
                del self.last_content[k]
        logger.debug("Auto-cleaned cache for run_id=%s", run_id)

    async def broadcast(self, run_id: str, data: Any):
        """특정 run_id를 구독 중인 모든 클라이언트에게 데이터 전송."""
        queues_to_send = []
        schedule_cleanup = False
        async with self.lock:
            # JSON 직렬화
            json_data = json.dumps(data, ensure_ascii=False)

            # 이벤트 타입별 캐싱 (늦은 구독자 재전송용)
            event_type = data.get("type")
            if event_type == "status":
                self.last_status[run_id] = json_data
                logger.debug("Cached last status for run_id=%s: %s", run_id, data.get("status"))
                if data.get("status") in self._TERMINAL_STATUSES:
                    schedule_cleanup = True
            elif event_type == "agent_message_created":
                if run_id not in self.agent_created:
                    self.agent_created[run_id] = []
                self.agent_created[run_id].append(json_data)
            elif event_type == "content":
                agent = data.get("agent", "")
                self.last_content[f"{run_id}:{agent}"] = json_data

            if run_id in self.queues:
                # 큐 목록 복사 (락 범위 축소)
                queues_to_send = list(self.queues[run_id])

        if schedule_cleanup:
            asyncio.create_task(self._schedule_cache_cleanup(run_id))

        if not queues_to_send:
            logger.debug("No subscribers for run_id=%s", run_id)
            return

        logger.debug("Broadcasting to %d subscribers for run_id=%s", len(queues_to_send), run_id)
        for queue in queues_to_send:
            await queue.put(json_data)

        # broadcast_sync 제거됨 (dead code + deprecated asyncio.get_event_loop 사용)

stream_manager = StreamManager()
