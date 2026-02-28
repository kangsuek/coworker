"""Claude CLI subprocess 관리 (PRD ADR-004).

핵심 구조:
- _call_claude_sync(): 동기 Popen + stdout 라인 루프
- call_claude_streaming(): asyncio.to_thread() 비동기 래퍼
- _cli_lock: Global Execution Lock (asyncio.Lock)
- LineBufferFlusher: 0.5초 간격 배치 DB 쓰기
"""

# TODO: Sprint 2에서 구현
