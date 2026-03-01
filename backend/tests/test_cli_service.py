"""CLI 서비스 테스트 — Task 2-1, 2-2.

테스트 대상:
- _call_claude_sync: Popen mock → stdout 라인 수신, 콜백, 타임아웃
- call_claude_streaming: asyncio.to_thread 래퍼
- LineBufferFlusher: 버퍼 append/flush, 스레드 안전성, stop 시 잔여 flush
- Global Execution Lock: 순차 실행, cancel_current
"""

import asyncio
import signal
import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.services.cli_service import (
    LineBufferFlusher,
    _call_claude_sync,
    call_claude_streaming,
    cancel_current,
    execute_with_lock,
)

# ---------------------------------------------------------------------------
# _call_claude_sync 테스트
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_popen():
    """subprocess.Popen을 mock하여 실제 CLI 호출 없이 테스트."""
    mock_proc = MagicMock()
    mock_proc.stdout = iter(["line1\n", "line2\n", "line3\n"])
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.wait.return_value = None
    mock_proc.returncode = 0
    mock_proc.pid = 12345
    return mock_proc


def test_call_claude_sync_returns_output(mock_popen):
    """mock Popen → stdout 라인 수신 → join된 문자열 반환."""
    with patch("subprocess.Popen", return_value=mock_popen):
        result = _call_claude_sync(
            system_prompt="You are helpful.",
            user_message="Hello",
        )
    assert result == "line1\nline2\nline3\n"


def test_call_claude_sync_calls_on_line_callback(mock_popen):
    """on_line 콜백이 각 stdout 라인마다 호출되는지 확인."""
    callback = MagicMock()
    with patch("subprocess.Popen", return_value=mock_popen):
        _call_claude_sync(
            system_prompt="You are helpful.",
            user_message="Hello",
            on_line=callback,
        )
    assert callback.call_count == 3
    callback.assert_any_call("line1\n")
    callback.assert_any_call("line2\n")
    callback.assert_any_call("line3\n")


def test_call_claude_sync_timeout(mock_popen):
    """타임아웃 초과 시 프로세스 그룹 종료 + RuntimeError 발생."""
    mock_popen.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="claude", timeout=1),
        None,  # killpg 후 두 번째 wait는 정상 종료
    ]
    mock_popen.poll.return_value = None

    with (
        patch("subprocess.Popen", return_value=mock_popen),
        patch("os.killpg") as mock_killpg,
        patch("os.getpgid", return_value=12345),
        pytest.raises(RuntimeError, match="timeout"),
    ):
        _call_claude_sync(
            system_prompt="You are helpful.",
            user_message="Hello",
            timeout=1,
        )
    mock_killpg.assert_called_once()


@pytest.mark.asyncio
async def test_call_claude_streaming_async(mock_popen):
    """asyncio.to_thread 래퍼가 정상 동작하는지 확인."""
    with patch("subprocess.Popen", return_value=mock_popen):
        result = await call_claude_streaming(
            system_prompt="You are helpful.",
            user_message="Hello",
        )
    assert "line1" in result


# ---------------------------------------------------------------------------
# LineBufferFlusher 테스트
# ---------------------------------------------------------------------------


def test_line_buffer_flusher_append_and_flush():
    """버퍼 추가 + 수동 flush → flush_callback에 전달."""
    flushed_lines: list[str] = []
    flusher = LineBufferFlusher(
        flush_callback=lambda lines: flushed_lines.extend(lines),
        flush_interval=10.0,  # 자동 flush 방지 (수동 테스트)
    )
    flusher.append("line-a")
    flusher.append("line-b")
    flusher.flush()

    assert flushed_lines == ["line-a", "line-b"]


def test_line_buffer_flusher_thread_safety():
    """5 threads x 100 lines = 500 lines, flush 후 데이터 무결성 확인."""
    flushed_lines: list[str] = []
    lock = threading.Lock()

    def safe_extend(lines):
        with lock:
            flushed_lines.extend(lines)

    flusher = LineBufferFlusher(
        flush_callback=safe_extend,
        flush_interval=0.05,
    )
    flusher.start()

    def append_many(start, count):
        for i in range(start, start + count):
            flusher.append(f"line-{i}")

    threads = [threading.Thread(target=append_many, args=(i * 100, 100)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    flusher.stop()
    assert len(flushed_lines) == 500


def test_line_buffer_flusher_stop_flushes_remaining():
    """stop 호출 시 버퍼에 남은 데이터가 모두 flush되는지 확인."""
    flushed_lines: list[str] = []
    flusher = LineBufferFlusher(
        flush_callback=lambda lines: flushed_lines.extend(lines),
        flush_interval=10.0,  # 자동 flush 방지
    )
    flusher.append("remaining-1")
    flusher.append("remaining-2")

    flusher.stop()
    assert flushed_lines == ["remaining-1", "remaining-2"]


# ---------------------------------------------------------------------------
# Global Execution Lock 테스트 (Task 2-2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_global_lock_sequential_execution():
    """동시 2개 execute_with_lock 호출 시 순차 실행 확인."""
    events: list[str] = []

    async def task_a():
        events.append("a_start")
        await asyncio.sleep(0.1)
        events.append("a_end")
        return "result_a"

    async def task_b():
        events.append("b_start")
        events.append("b_end")
        return "result_b"

    result_a, result_b = await asyncio.gather(
        execute_with_lock(task_a()),
        execute_with_lock(task_b()),
    )

    assert result_a == "result_a"
    assert result_b == "result_b"
    assert events.index("a_end") < events.index("b_start")


@pytest.mark.asyncio
async def test_cancel_current_kills_process_group():
    """cancel_current 호출 시 os.killpg(pgid, SIGTERM) 실행 확인."""
    import app.services.cli_service as mod

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # 아직 실행 중
    mock_proc.pid = 99999

    original = mod._current_proc
    mod._current_proc = mock_proc
    try:
        with (
            patch("os.killpg") as mock_killpg,
            patch("os.getpgid", return_value=99999),
        ):
            await cancel_current()
        mock_killpg.assert_called_once_with(99999, signal.SIGTERM)
    finally:
        mod._current_proc = original


@pytest.mark.asyncio
async def test_cancel_current_handles_no_process():
    """_current_proc이 None일 때 cancel_current가 예외 없이 반환."""
    import app.services.cli_service as mod

    original = mod._current_proc
    mod._current_proc = None
    try:
        await cancel_current()  # 예외 없이 정상 반환
    finally:
        mod._current_proc = original
