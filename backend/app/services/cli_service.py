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
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.services import settings_service

logger = logging.getLogger(__name__)

_active_procs: dict[str, list[subprocess.Popen]] = {}
_active_procs_lock = threading.Lock()  # _active_procs 다중 스레드 접근 보호
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
    model: str = (kwargs.get("model") or "").strip()

    file_paths: list[str] = kwargs.get("file_paths") or []

    # Claude CLI는 cwd="/tmp" 워크스페이스 외부 파일에 접근 불가.
    # 업로드 파일을 /tmp에 복사하여 워크스페이스 안으로 이동시킨 뒤 프롬프트에 경로 포함.
    # (--file 옵션은 Files API file_id 전용이므로 로컬 경로에 사용 불가)
    tmp_dir: str | None = None
    tmp_file_paths: list[str] = []
    if file_paths:
        tmp_dir = tempfile.mkdtemp(prefix="coworker_", dir="/tmp")
        for fp in file_paths:
            dst = os.path.join(tmp_dir, os.path.basename(fp))
            shutil.copy2(fp, dst)
            tmp_file_paths.append(dst)

    message_with_files = user_message
    if tmp_file_paths:
        file_refs = "\n".join(f"- {fp}" for fp in tmp_file_paths)
        message_with_files += f"\n\n[ATTACHED FILES - Please read and analyze these files]\n{file_refs}\n[END ATTACHED FILES]"

    cli_path = settings_service.get("claude_cli_path") or settings.claude_cli_path
    cmd = [cli_path, "-p", message_with_files, "--system-prompt", system_prompt]
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
    # PATH 보강: 패키징 앱은 PATH=/usr/bin:/bin만 제공 — node/cli 도구 경로 추가
    _extra = "/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin"
    child_env["PATH"] = _extra + ":" + child_env.get("PATH", "")

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
    with _active_procs_lock:
        _active_procs.setdefault(proc_key, []).append(proc)

    # Popen 직후 취소 여부 재확인 (Race condition 방어)
    if run_id and run_id in _cancelled_runs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        with _active_procs_lock:
            procs = _active_procs.get(proc_key, [])
            if proc in procs:
                procs.remove(proc)
        raise RuntimeError(f"Run {run_id} cancelled during startup")

    # output_json=True: 줄 누적 후 반환 / output_json=False: NDJSON 파싱 (오류 보고용 raw 보관)
    collected: list[str] = []
    final_result = ""   # stream-json 모드 전용: result 이벤트에서 추출
    chunks: list[str] = []  # delta 청크 누적 (result 이벤트 파싱 실패 시 폴백)
    try:
        for line in proc.stdout:
            # 루프 내에서 취소 여부 수시 확인
            if run_id and run_id in _cancelled_runs:
                logger.info("Claude CLI 실행 중 중단: run_id=%s", run_id)
                on_line = None  # 취소 후 잔여 버퍼 데이터 콜백 차단
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
                    logger.debug("Claude CLI NDJSON 파싱 실패 (무시): run_id=%s, line=%r", run_id, stripped[:120])
                    continue

                t = obj.get("type")
                if t == "stream_event":
                    ev = obj.get("event", {})
                    if ev.get("type") == "content_block_delta":
                        delta = ev.get("delta", {})
                        if delta.get("type") == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                chunks.append(chunk)
                                if on_line:
                                    try:
                                        on_line(chunk)
                                    except Exception:
                                        logger.debug("on_line 콜백 예외 무시 (스트림 유지): run_id=%s", run_id)
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
        with _active_procs_lock:
            procs = _active_procs.get(proc_key, [])
            if proc in procs:
                procs.remove(proc)
            if not procs and proc_key in _active_procs:
                del _active_procs[proc_key]
        # /tmp 임시 디렉토리 정리
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # 취소로 인한 종료인 경우 예외 발생
    if run_id and run_id in _cancelled_runs:
        raise RuntimeError(f"Run {run_id} was cancelled")

    if proc.returncode != 0:
        logger.error("Claude CLI 비정상 종료: rc=%d, output_lines=%d", proc.returncode, len(collected))
        raise RuntimeError(f"Claude CLI error (rc={proc.returncode}): {''.join(collected)}")

    logger.info(
        "Claude CLI 완료: rc=%d, output_lines=%d, final_result_len=%d, chunks=%d",
        proc.returncode, len(collected), len(final_result), len(chunks),
    )
    # 진단용: final_result/chunks 모두 비어 있으면 마지막 20줄 로깅
    if not output_json and not final_result and not chunks:
        sample = collected[-20:] if len(collected) > 20 else collected
        logger.warning("Claude CLI 응답 비어 있음. 마지막 출력:\n%s", "".join(sample))

    if output_json:
        return "".join(collected)
    # final_result이 없으면 delta 청크 누적값 폴백 (Claude CLI 출력 포맷 변경 대응)
    if not final_result and chunks:
        logger.warning("Claude CLI result 이벤트 없음, delta 청크 누적값으로 폴백: run_id=%s, chunks=%d", run_id, len(chunks))
    return final_result or "".join(chunks)


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


async def execute_if_not_cancelled(coro, run_id: str | None = None):
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
        with _active_procs_lock:
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
    with _active_procs_lock:
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


def get_active_cli_count() -> int:
    """현재 실행 중인 CLI 프로세스 수 반환."""
    with _active_procs_lock:
        return sum(len(procs) for procs in _active_procs.values())


class LineBufferFlusher:
    """비동기 배치 flush 버퍼.

    Popen stdout 라인을 thread-safe queue에 모아두고,
    비동기 태스크가 주기적으로 비동기 flush_callback을 호출한다.

    BUG-M01 수정: threading.Lock 대신 queue.Queue 사용하여
    이벤트 루프 블로킹 방지 (append는 별도 스레드, flush는 이벤트 루프에서 실행).
    """

    def __init__(self, flush_callback: Callable[[list[str]], Coroutine[Any, Any, None]], flush_interval: float = 0.5):
        self._flush_callback = flush_callback
        self._flush_interval = flush_interval
        self._queue: queue.Queue[str] = queue.Queue()  # thread-safe, 이벤트 루프 비블로킹
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def append(self, line: str) -> None:
        """버퍼에 라인 추가 (동기 호출 가능, 이벤트 루프 블로킹 없음)."""
        self._queue.put_nowait(line)

    async def flush(self) -> None:
        """큐에 쌓인 항목을 비동기 콜백으로 전달."""
        snapshot: list[str] = []
        while True:
            try:
                snapshot.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not snapshot:
            return
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
