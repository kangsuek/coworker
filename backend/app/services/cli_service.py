"""Claude CLI subprocess 관리 (PRD ADR-004).

핵심 구조:
- _call_claude_sync(): 동기 Popen + stdout 라인 루프
- call_claude_streaming(): asyncio.to_thread() 비동기 래퍼
- _cli_lock: Global Execution Lock (asyncio.Lock) — Task 2-2에서 구현
- LineBufferFlusher: 0.5초 간격 배치 DB 쓰기
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import threading
from collections.abc import Callable

from app.config import settings

logger = logging.getLogger(__name__)

_current_proc: subprocess.Popen | None = None
_cli_lock = asyncio.Lock()
# cancel race condition 방어: Popen 직전에 취소 요청이 들어온 경우를 감지
_is_cancelled: bool = False


def _call_claude_sync(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """동기 함수: subprocess.Popen으로 Claude CLI 실행, stdout 라인별 스트리밍.

    Args:
        system_prompt: 시스템 프롬프트
        user_message: 사용자 메시지
        on_line: 각 stdout 라인마다 호출될 콜백
        **kwargs: output_json (bool), timeout (int)
    """
    global _current_proc, _is_cancelled

    _is_cancelled = False  # 이전 취소 상태 초기화
    output_json: bool = kwargs.get("output_json", False)
    timeout: int = kwargs.get("timeout", settings.claude_cli_timeout)

    cmd = [settings.claude_cli_path, "-p", user_message, "--system-prompt", system_prompt]
    if output_json:
        cmd.extend(["--output-format", "json"])
    logger.debug("Claude CLI 시작: output_json=%s, timeout=%ds", output_json, timeout)

    # CLAUDECODE 환경변수 제거: Claude Code 세션 내에서 중첩 실행 방지
    child_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # stderr를 stdout에 합쳐 파이프 버퍼 포화로 인한 deadlock 방지
        text=True,
        start_new_session=True,
        bufsize=1,
        env=child_env,
    )

    # Popen과 _current_proc 할당 사이에 cancel 요청이 들어온 경우 즉시 종료
    if _is_cancelled:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        proc.wait()
        raise RuntimeError("Cancelled before execution")

    _current_proc = proc

    lines: list[str] = []
    try:
        for line in proc.stdout:
            lines.append(line)
            if on_line:
                on_line(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        proc.wait()
        logger.error("Claude CLI 타임아웃: pid=%d, timeout=%ds", proc.pid, timeout)
        raise RuntimeError(f"CLI timeout after {timeout}s")
    finally:
        _current_proc = None

    if proc.returncode != 0:
        # stderr는 stdout에 합쳐졌으므로 이미 lines에 포함됨
        logger.error("Claude CLI 비정상 종료: rc=%d, output_lines=%d", proc.returncode, len(lines))
        raise RuntimeError(f"Claude CLI error (rc={proc.returncode}): {''.join(lines)}")

    logger.info("Claude CLI 완료: rc=%d, output_lines=%d", proc.returncode, len(lines))
    return "".join(lines)


async def call_claude_streaming(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """비동기 래퍼: asyncio.to_thread()로 _call_claude_sync를 별도 스레드에서 실행."""
    return await asyncio.to_thread(
        _call_claude_sync, system_prompt, user_message, on_line, **kwargs
    )


async def execute_with_lock(coro):
    """Lock 획득 후 코루틴 실행. 대기 중이면 queued 상태."""
    async with _cli_lock:
        return await coro


async def cancel_current():
    """현재 실행 중인 CLI 프로세스 + 자식 프로세스 전체 종료."""
    global _is_cancelled
    _is_cancelled = True  # Popen 직전 취소 요청 대비 플래그 설정
    if _current_proc and _current_proc.poll() is None:
        logger.info("Claude CLI 취소 요청: pid=%d", _current_proc.pid)
        try:
            os.killpg(os.getpgid(_current_proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass


class LineBufferFlusher:
    """0.5초 간격 배치 flush 버퍼.

    Popen stdout 라인을 인메모리 버퍼에 모아두고,
    단일 데몬 스레드가 주기적으로 flush_callback을 호출한다.
    threading.Timer 반복 생성 대신 Event.wait()를 사용해 스레드 오버헤드를 최소화한다.
    버퍼 스왑 패턴으로 Lock 보유 시간을 최소화한다.
    """

    def __init__(self, flush_callback: Callable[[list[str]], None], flush_interval: float = 0.5):
        self._flush_callback = flush_callback
        self._flush_interval = flush_interval
        self._lock = threading.Lock()
        self._buffer: list[str] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def append(self, line: str) -> None:
        """Lock 획득 → 버퍼에 라인 추가."""
        with self._lock:
            self._buffer.append(line)

    def flush(self) -> None:
        """Lock 획득 → 버퍼 스왑(교체+초기화) → Lock 해제 → 스왑된 데이터로 콜백 호출."""
        with self._lock:
            if not self._buffer:
                return
            snapshot = self._buffer
            self._buffer = []

        self._flush_callback(snapshot)

    def _run(self) -> None:
        """데몬 스레드 루프: stop_event가 설정될 때까지 주기적으로 flush."""
        # wait()가 timeout 안에 이벤트가 설정되면 True, 타임아웃이면 False 반환
        while not self._stop_event.wait(timeout=self._flush_interval):
            self.flush()

    def start(self) -> None:
        """단일 데몬 스레드 시작."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """스레드 종료 신호 + 잔여 버퍼 최종 flush."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self.flush()
