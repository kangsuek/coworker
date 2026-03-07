"""Claude CLI subprocess 관리 (PRD ADR-004).

핵심 구조:
- _call_claude_sync(): 동기 Popen + stdout 라인 루프
- call_claude_streaming(): asyncio.to_thread() 비동기 래퍼
- _cli_lock: Global Execution Lock (asyncio.Lock) — Task 2-2에서 구현
- LineBufferFlusher: 0.5초 간격 배치 DB 쓰기
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_active_procs: dict[str, list[subprocess.Popen]] = {}
# 특정 run_id의 취소 상태를 추적
_cancelled_runs: set[str] = set()

_UNTRACKED_KEY = "__untracked__"


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
        on_line: 각 토큰 청크마다 호출될 콜백 (stream-json 모드)
        **kwargs: output_json (bool), timeout (int), run_id (str)

    output_json=True : --output-format json  (분류 전용, 완료 후 JSON 1개 반환)
    output_json=False: --output-format stream-json --verbose --include-partial-messages
                       (실시간 토큰 스트리밍, on_line 콜백으로 청크 전달)
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
    else:
        # 실시간 토큰 스트리밍: stream-json + verbose (필수) + include-partial-messages
        cmd.extend(["--output-format", "stream-json", "--verbose", "--include-partial-messages"])
    logger.debug("Claude CLI 시작: run_id=%s, model=%s, output_json=%s", run_id, model, output_json)

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

    # 활성 프로세스 등록 (run_id 키로 분리)
    proc_key = run_id or _UNTRACKED_KEY
    _active_procs.setdefault(proc_key, []).append(proc)

    # Popen 직후 취소 여부 재확인 (Race condition 방어)
    if run_id and run_id in _cancelled_runs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        procs = _active_procs.get(proc_key, [])
        if proc in procs:
            procs.remove(proc)
        raise RuntimeError(f"Run {run_id} cancelled during startup")

    # output_json=True: 줄 누적 후 반환 / output_json=False: NDJSON 파싱 (오류 보고용 raw 보관)
    collected: list[str] = []
    final_result = ""  # stream-json 모드 전용: result 이벤트에서 추출
    try:
        for line in proc.stdout:
            # 루프 내에서 취소 여부 수시 확인
            if run_id and run_id in _cancelled_runs:
                logger.info("Claude CLI 실행 중 중단: run_id=%s", run_id)
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
                break

            collected.append(line)

            if output_json:
                # json 모드: 전체 줄을 그대로 콜백 전달 (분류용)
                if on_line:
                    on_line(line)
            else:
                # stream-json 모드: NDJSON 파싱하여 토큰 청크만 on_line 전달
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                t = obj.get("type")
                if t == "stream_event":
                    ev = obj.get("event", {})
                    if ev.get("type") == "content_block_delta":
                        delta = ev.get("delta", {})
                        if delta.get("type") == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk and on_line:
                                on_line(chunk)
                elif t == "result" and obj.get("subtype") == "success":
                    final_result = obj.get("result", "")

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
        procs = _active_procs.get(proc_key, [])
        if proc in procs:
            procs.remove(proc)
        if not procs and proc_key in _active_procs:
            del _active_procs[proc_key]

    # 취소로 인한 종료인 경우 예외 발생
    if run_id and run_id in _cancelled_runs:
        raise RuntimeError(f"Run {run_id} was cancelled")

    if proc.returncode != 0:
        logger.error("Claude CLI 비정상 종료: rc=%d, output_lines=%d", proc.returncode, len(collected))
        raise RuntimeError(f"Claude CLI error (rc={proc.returncode}): {''.join(collected)}")

    logger.info("Claude CLI 완료: rc=%d, output_lines=%d", proc.returncode, len(collected))

    if output_json:
        return "".join(collected)
    return final_result


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
    """실행 전 취소 여부 확인 후 코루틴 실행."""
    if run_id and run_id in _cancelled_runs:
        logger.info("이미 취소된 Run: run_id=%s", run_id)
        raise RuntimeError(f"Run {run_id} was cancelled")
    return await coro


async def cancel_current(run_id: str | None = None):
    """현재 실행 중인 CLI 프로세스 종료 및 취소 목록 등록.

    run_id가 주어지면 해당 run의 프로세스만 종료.
    run_id=None이면 전체 종료 (서버 종료 시 사용).
    """
    if run_id:
        _cancelled_runs.add(run_id)
        procs = list(_active_procs.get(run_id, []))
        if not procs:
            return
        logger.info("Claude CLI 취소 요청 (단일 run): run_id=%s, count=%d", run_id, len(procs))
        for proc in procs:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
        return

    # run_id=None: 전체 종료
    all_procs = [p for procs in _active_procs.values() for p in procs]
    if not all_procs:
        return

    logger.info("Claude CLI 취소 요청 (전체): count=%d", len(all_procs))
    for proc in all_procs:
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
