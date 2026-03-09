"""Gemini CLI Provider implementation."""

import asyncio
import json
import logging
import os
import signal
import subprocess
from collections.abc import Callable

from app.config import settings
from .base import LLMProvider
from app.services.cli_service import execute_if_not_cancelled, _cancelled_runs

logger = logging.getLogger(__name__)

def _call_gemini_sync(
    system_prompt: str,
    user_message: str,
    on_line: Callable[[str], None] | None = None,
    **kwargs,
) -> str:
    """동기 함수: subprocess.Popen으로 Gemini CLI 실행, stream-json 실시간 스트리밍.

    --output-format stream-json 으로 실행하여 delta message 이벤트를 실시간으로
    on_line 콜백에 전달한다. 각 delta chunk를 누적하여 최종 전체 텍스트를 반환한다.

    Gemini stream-json 이벤트 구조:
      {"type":"message","role":"assistant","content":"<증분 청크>","delta":true}
      {"type":"result","status":"success",...}
    """
    import app.services.cli_service as cli_service

    run_id: str | None = kwargs.get("run_id")
    proc_key = run_id or cli_service._UNTRACKED_KEY
    timeout: int = kwargs.get("timeout", settings.claude_cli_timeout)
    model: str = kwargs.get("model", "")

    # Gemini CLI 호출 명령어 구성 (stream-json 실시간 스트리밍)
    # SEC-04: 명시적 구분자로 시스템/사용자 영역 분리 (프롬프트 인젝션 완화)
    combined_prompt = (
        f"[SYSTEM INSTRUCTIONS]\n{system_prompt}\n[END SYSTEM INSTRUCTIONS]"
        f"\n\n[USER MESSAGE]\n{user_message}\n[END USER MESSAGE]"
    )
    file_paths: list[str] = kwargs.get("file_paths") or []

    cmd = ["gemini", "-p", combined_prompt]
    if model:
        cmd.extend(["--model", model])
    for fp in file_paths:
        cmd.extend(["--image", fp])
    cmd.extend(["--output-format", "stream-json"])

    logger.debug("Gemini CLI 시작: run_id=%s, model=%s", run_id, model)

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
        cwd="/tmp",  # GEMINI.md 자동 로드 방지 (프로젝트 컨텍스트 오염 차단)
    )

    # 활성 프로세스 등록 (run_id 키로 분리)
    cli_service._active_procs.setdefault(proc_key, []).append(proc)

    if run_id and run_id in cli_service._cancelled_runs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
        procs = cli_service._active_procs.get(proc_key, [])
        if proc in procs:
            procs.remove(proc)
        raise RuntimeError(f"Run {run_id} cancelled during startup")

    # NDJSON 파싱: delta 청크 누적 → on_line 실시간 전달, 오류 보고용 raw 보관
    collected: list[str] = []
    chunks: list[str] = []  # delta 청크 누적 (최종 반환값 조립용)
    try:
        for line in proc.stdout:
            # 루프 내 취소 확인
            if run_id and run_id in cli_service._cancelled_runs:
                logger.info("Gemini CLI 실행 중 중단: run_id=%s", run_id)
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
                break

            collected.append(line)
            stripped = line.strip()
            if not stripped:
                continue

            # 비-JSON 시스템 메시지 무시 (e.g. "Loaded cached credentials.")
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            t = obj.get("type")
            if t == "message" and obj.get("role") == "assistant" and obj.get("delta"):
                chunk = obj.get("content", "")
                if chunk:
                    chunks.append(chunk)
                    if on_line:
                        on_line(chunk)

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
        procs = cli_service._active_procs.get(proc_key, [])
        if proc in procs:
            procs.remove(proc)
        if not procs and proc_key in cli_service._active_procs:
            del cli_service._active_procs[proc_key]

    if run_id and run_id in cli_service._cancelled_runs:
        raise RuntimeError(f"Run {run_id} was cancelled")

    if proc.returncode != 0:
        logger.error("Gemini CLI 비정상 종료: rc=%d, output_lines=%d", proc.returncode, len(collected))
        raise RuntimeError(f"Gemini CLI error (rc={proc.returncode}): {''.join(collected)}")

    logger.info("Gemini CLI 완료: rc=%d, chunks=%d", proc.returncode, len(chunks))
    return "".join(chunks)


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
        return await execute_if_not_cancelled(
            call_gemini_streaming(
                system_prompt=system_prompt,
                user_message=user_message,
                on_line=on_line,
                model=model,
                **kwargs
            ),
            run_id=run_id
        )
