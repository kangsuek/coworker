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

_active_procs: set[subprocess.Popen] = set()
# 특정 run_id의 취소 상태를 추적
_cancelled_runs: set[str] = set()


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
        **kwargs: output_json (bool), timeout (int), run_id (str)
    """
    run_id: str | None = kwargs.get("run_id")
    output_json: bool = kwargs.get("output_json", False)
    timeout: int = kwargs.get("timeout", settings.claude_cli_timeout)

    model: str = kwargs.get("model", "")

    cmd = [settings.claude_cli_path, "-p", user_message, "--system-prompt", system_prompt]
    if model:
        cmd.extend(["--model", model])
    if output_json:
        cmd.extend(["--output-format", "json"])
    logger.debug("Claude CLI 시작: run_id=%s, model=%s", run_id, model)

    # CLAUDECODE 환경변수 제거: Claude Code 세션 내에서 중첩 실행 방지
    child_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    # Popen 직전 취소 여부 확인
    if run_id and run_id in _cancelled_runs:
        logger.info("Claude CLI 실행 전 취소됨: run_id=%s", run_id)
        raise RuntimeError(f"Run {run_id} cancelled before execution")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # stderr를 stdout에 합쳐 파이프 버퍼 포화로 인한 deadlock 방지
        text=True,
        start_new_session=True,
        bufsize=1,
        env=child_env,
        cwd="/tmp",  # CLAUDE.md 자동 로드 방지 (프로젝트 컨텍스트 오염 차단)
    )

    # 활성 프로세스 집합에 추가
    _active_procs.add(proc)

    # Popen 직후 취소 여부 재확인 (Race condition 방어)
    if run_id and run_id in _cancelled_runs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        if proc in _active_procs:
            _active_procs.remove(proc)
        raise RuntimeError(f"Run {run_id} cancelled during startup")

    lines: list[str] = []
    try:
        for line in proc.stdout:
            # 루프 내에서 취소 여부 수시 확인 (Bug 1.4 방어)
            if run_id and run_id in _cancelled_runs:
                logger.info("Claude CLI 실행 중 중단: run_id=%s", run_id)
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                break

            lines.append(line)
            if on_line:
                on_line(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        logger.error("Claude CLI 타임아웃: pid=%d, timeout=%ds", proc.pid, timeout)
        raise RuntimeError(f"CLI timeout after {timeout}s")
    except Exception:
        # 기타 예외 발생 시 프로세스 정리
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        raise
    finally:
        if proc in _active_procs:
            _active_procs.remove(proc)

    # 취소로 인한 종료인 경우 예외 발생
    if run_id and run_id in _cancelled_runs:
        raise RuntimeError(f"Run {run_id} was cancelled")

    if proc.returncode != 0:
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


async def execute_with_lock(coro, run_id: str | None = None):
    """실행 전 취소 여부 확인 후 코루틴 실행. (이전의 전역 락은 제거됨)"""
    if run_id and run_id in _cancelled_runs:
        logger.info("이미 취소된 Run: run_id=%s", run_id)
        raise RuntimeError(f"Run {run_id} was cancelled")
    return await coro


async def cancel_current(run_id: str | None = None):
    """현재 실행 중인 CLI 프로세스 전체 종료 및 취소 목록 등록."""
    if run_id:
        _cancelled_runs.add(run_id)
    
    if not _active_procs:
        return

    logger.info("Claude CLI 취소 요청 (일괄 종료): count=%d", len(_active_procs))
    for proc in list(_active_procs):
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass


class LineBufferFlusher:
    """비동기 배치 flush 버퍼.

    Popen stdout 라인을 인메모리 버퍼에 모아두고,
    비동기 태스크가 주기적으로 비동기 flush_callback을 호출한다.
    모든 DB 쓰기 작업이 동일한 비동기 락(db_lock)을 사용할 수 있게 한다.
    """

    def __init__(self, flush_callback: Callable[[list[str]], Coroutine[Any, Any, None]], flush_interval: float = 0.5):
        self._flush_callback = flush_callback
        self._flush_interval = flush_interval
        self._lock = threading.Lock()  # 버퍼 접근용 동기 락 (append는 stdout 루프에서 호출됨)
        self._buffer: list[str] = []
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def append(self, line: str) -> None:
        """버퍼에 라인 추가 (동기 호출 가능)."""
        with self._lock:
            self._buffer.append(line)

    async def flush(self) -> None:
        """버퍼 스왑 후 비동기 콜백 호출."""
        with self._lock:
            if not self._buffer:
                return
            snapshot = self._buffer
            self._buffer = []

        await self._flush_callback(snapshot)

    async def _run_loop(self) -> None:
        """비동기 루프: stop_event가 설정될 때까지 주기적으로 flush."""
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(self._flush_interval)
                await self.flush()
        except asyncio.CancelledError:
            pass
        finally:
            await self.flush()

    def start(self) -> None:
        """비동기 루프 태스크 시작."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """비동기 루프 중지 및 최종 flush."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.flush()
