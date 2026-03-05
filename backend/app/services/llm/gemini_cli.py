"""Gemini CLI Provider implementation."""

import asyncio
import logging
import os
import signal
import subprocess
from collections.abc import Callable

from app.config import settings
from .base import LLMProvider
from app.services.cli_service import execute_with_lock, _cancelled_runs, _active_procs

logger = logging.getLogger(__name__)

def _call_gemini_sync(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """동기 함수: subprocess.Popen으로 Gemini CLI 실행, stdout 라인별 스트리밍."""
    import app.services.cli_service as cli_service

    run_id: str | None = kwargs.get("run_id")
    timeout: int = kwargs.get("timeout", settings.claude_cli_timeout)
    model: str = kwargs.get("model", "")

    # Gemini CLI 호출 명령어 구성
    combined_prompt = f"System: {system_prompt}\n\nUser: {user_message}"
    cmd = ["gemini", "-p", combined_prompt]
    if model:
        cmd.extend(["--model", model])

    logger.debug("Gemini CLI 시작: run_id=%s, timeout=%ds", run_id, timeout)

    # Popen 직전 취소 확인
    if run_id and run_id in cli_service._cancelled_runs:
        logger.info("Gemini CLI 실행 전 취소됨: run_id=%s", run_id)
        raise RuntimeError(f"Run {run_id} cancelled before execution")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
        bufsize=1,
    )

    # 활성 프로세스 추적
    _active_procs.add(proc)

    if run_id and run_id in cli_service._cancelled_runs:
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
            # 루프 내 취소 확인
            if run_id and run_id in cli_service._cancelled_runs:
                logger.info("Gemini CLI 실행 중 중단: run_id=%s", run_id)
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                break

            # Gemini CLI의 불필요한 시스템 메시지 필터링
            if line.startswith("Loaded cached credentials") or line.startswith("[WARNING] --raw-output"):
                continue
            
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
        logger.error("Gemini CLI 타임아웃: pid=%d, timeout=%ds", proc.pid, timeout)
        raise RuntimeError(f"CLI timeout after {timeout}s")
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        raise
    finally:
        if proc in _active_procs:
            _active_procs.remove(proc)

    if run_id and run_id in cli_service._cancelled_runs:
        raise RuntimeError(f"Run {run_id} was cancelled")

    if proc.returncode != 0:
        logger.error("Gemini CLI 비정상 종료: rc=%d, output_lines=%d", proc.returncode, len(lines))
        raise RuntimeError(f"Gemini CLI error (rc={proc.returncode}): {''.join(lines)}")

    logger.info("Gemini CLI 완료: rc=%d, output_lines=%d", proc.returncode, len(lines))
    return "".join(lines)


async def call_gemini_streaming(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """비동기 래퍼: asyncio.to_thread()로 _call_gemini_sync를 별도 스레드에서 실행."""
    return await asyncio.to_thread(
        _call_gemini_sync, system_prompt, user_message, on_line, **kwargs
    )


class GeminiCliProvider(LLMProvider):
    async def stream_generate(
        self,
        system_prompt: str,
        user_message: str,
        on_line: Callable[[str], None] | None = None,
        model: str = "",
        **kwargs,
    ) -> str:
        """Gemini CLI를 통해 모델을 호출합니다."""
        run_id = kwargs.get("run_id")
        return await execute_with_lock(
            call_gemini_streaming(
                system_prompt=system_prompt,
                user_message=user_message,
                on_line=on_line,
                model=model,
                **kwargs
            ),
            run_id=run_id
        )
