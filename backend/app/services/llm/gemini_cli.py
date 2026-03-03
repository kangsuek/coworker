"""Gemini CLI Provider implementation."""

import asyncio
import logging
import os
import signal
import subprocess
from collections.abc import Callable

from app.config import settings
from .base import LLMProvider
from app.services.cli_service import execute_with_lock, _is_cancelled, _current_proc

logger = logging.getLogger(__name__)

def _call_gemini_sync(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """동기 함수: subprocess.Popen으로 Gemini CLI 실행, stdout 라인별 스트리밍."""
    from app.services.cli_service import _is_cancelled, _current_proc
    import app.services.cli_service as cli_service

    cli_service._is_cancelled = False
    timeout: int = kwargs.get("timeout", settings.claude_cli_timeout)
    model: str = kwargs.get("model", "")

    # Gemini CLI 호출 명령어 구성
    # gemini -p "<user_message>"
    # 현재 gemini cli는 --system 옵션이 없으므로 prompt에 포함
    combined_prompt = f"System: {system_prompt}\n\nUser: {user_message}"
    cmd = ["gemini", "-p", combined_prompt]
    if model:
        cmd.extend(["--model", model])

    logger.debug("Gemini CLI 시작: timeout=%ds", timeout)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
        bufsize=1,
    )

    if cli_service._is_cancelled:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        raise RuntimeError("Cancelled before execution")

    cli_service._current_proc = proc

    lines: list[str] = []
    try:
        for line in proc.stdout:
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
    finally:
        cli_service._current_proc = None

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
        return await execute_with_lock(
            call_gemini_streaming(
                system_prompt=system_prompt,
                user_message=user_message,
                on_line=on_line,
                model=model,
                **kwargs
            )
        )
