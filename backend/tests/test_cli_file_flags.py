"""Phase 3 CLI 파일 플래그 TDD 테스트

CLI-01: LLMProvider base interface file_paths 파라미터
CLI-02a: Claude CLI _call_claude_sync → --file 플래그
CLI-02b: Gemini CLI _call_gemini_sync → --image 플래그
"""

import subprocess
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ───────────────────────────────────────────────
# 공통 fixture
# ───────────────────────────────────────────────


@pytest.fixture
def mock_proc_factory():
    """subprocess.Popen mock 생성 헬퍼."""
    def _make(stdout_lines: list[str] | None = None, returncode: int = 0):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(stdout_lines or [])
        mock_proc.wait.return_value = None
        mock_proc.returncode = returncode
        mock_proc.pid = 12345
        mock_proc.poll.return_value = returncode
        return mock_proc
    return _make


# ───────────────────────────────────────────────
# CLI-01: LLMProvider 인터페이스
# ───────────────────────────────────────────────


def test_llm_provider_stream_generate_accepts_file_paths():
    """LLMProvider.stream_generate 시그니처에 file_paths 파라미터가 있어야 한다."""
    import inspect
    from app.services.llm.base import LLMProvider

    sig = inspect.signature(LLMProvider.stream_generate)
    assert "file_paths" in sig.parameters


def test_claude_provider_stream_generate_accepts_file_paths():
    """ClaudeCliProvider.stream_generate가 file_paths를 수용해야 한다."""
    import inspect
    from app.services.llm.claude_cli import ClaudeCliProvider

    sig = inspect.signature(ClaudeCliProvider.stream_generate)
    assert "file_paths" in sig.parameters or "kwargs" in str(sig)


def test_gemini_provider_stream_generate_accepts_file_paths():
    """GeminiCliProvider.stream_generate가 file_paths를 수용해야 한다."""
    import inspect
    from app.services.llm.gemini_cli import GeminiCliProvider

    sig = inspect.signature(GeminiCliProvider.stream_generate)
    assert "file_paths" in sig.parameters or "kwargs" in str(sig)


# ───────────────────────────────────────────────
# CLI-02a: Claude CLI --file 플래그
# ───────────────────────────────────────────────


def test_claude_cli_adds_file_flag_for_each_path(mock_proc_factory):
    """file_paths 전달 시 cmd에 --file 플래그가 파일 수만큼 추가되어야 한다."""
    from app.services.cli_service import _call_claude_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="hello",
            output_json=True,
            file_paths=["/tmp/photo.jpg", "/tmp/chart.png"],
        )

    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "--file" in cmd
    # 두 파일 모두 전달
    file_indices = [i for i, v in enumerate(cmd) if v == "--file"]
    assert len(file_indices) == 2
    assert cmd[file_indices[0] + 1] == "/tmp/photo.jpg"
    assert cmd[file_indices[1] + 1] == "/tmp/chart.png"


def test_claude_cli_no_file_flag_when_empty(mock_proc_factory):
    """file_paths=[] 또는 미전달 시 --file 플래그가 없어야 한다."""
    from app.services.cli_service import _call_claude_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="hello",
            output_json=True,
            file_paths=[],
        )

    assert "--file" not in captured_cmds[0]


def test_claude_cli_no_file_flag_when_not_provided(mock_proc_factory):
    """file_paths 미전달 시 --file 플래그가 없어야 한다."""
    from app.services.cli_service import _call_claude_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="hello",
            output_json=True,
        )

    assert "--file" not in captured_cmds[0]


def test_claude_cli_file_flags_appear_before_output_format(mock_proc_factory):
    """--file 플래그는 --output-format 이전에 위치해야 한다 (CLI 파싱 순서)."""
    from app.services.cli_service import _call_claude_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="hello",
            output_json=True,
            file_paths=["/tmp/img.jpg"],
        )

    cmd = captured_cmds[0]
    file_idx = cmd.index("--file")
    output_idx = cmd.index("--output-format")
    assert file_idx < output_idx


def test_claude_cli_single_file(mock_proc_factory):
    """단일 파일 전달 시 --file 1개만 추가."""
    from app.services.cli_service import _call_claude_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="hello",
            output_json=True,
            file_paths=["/tmp/report.pdf"],
        )

    cmd = captured_cmds[0]
    assert cmd.count("--file") == 1
    assert "/tmp/report.pdf" in cmd


# ───────────────────────────────────────────────
# CLI-02b: Gemini CLI --image 플래그
# ───────────────────────────────────────────────


def test_gemini_cli_adds_image_flag_for_each_path(mock_proc_factory):
    """file_paths 전달 시 cmd에 --image 플래그가 파일 수만큼 추가되어야 한다."""
    from app.services.llm.gemini_cli import _call_gemini_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_gemini_sync(
            system_prompt="system",
            user_message="describe",
            file_paths=["/tmp/photo.jpg", "/tmp/chart.png"],
        )

    cmd = captured_cmds[0]
    assert "--image" in cmd
    image_indices = [i for i, v in enumerate(cmd) if v == "--image"]
    assert len(image_indices) == 2
    assert cmd[image_indices[0] + 1] == "/tmp/photo.jpg"
    assert cmd[image_indices[1] + 1] == "/tmp/chart.png"


def test_gemini_cli_no_image_flag_when_empty(mock_proc_factory):
    """file_paths=[] 시 --image 플래그가 없어야 한다."""
    from app.services.llm.gemini_cli import _call_gemini_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_gemini_sync(
            system_prompt="system",
            user_message="hello",
            file_paths=[],
        )

    assert "--image" not in captured_cmds[0]


def test_gemini_cli_no_image_flag_when_not_provided(mock_proc_factory):
    """file_paths 미전달 시 --image 플래그가 없어야 한다."""
    from app.services.llm.gemini_cli import _call_gemini_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_gemini_sync(
            system_prompt="system",
            user_message="hello",
        )

    assert "--image" not in captured_cmds[0]


def test_gemini_cli_single_image(mock_proc_factory):
    """단일 이미지 전달 시 --image 1개만 추가."""
    from app.services.llm.gemini_cli import _call_gemini_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_gemini_sync(
            system_prompt="system",
            user_message="explain",
            file_paths=["/tmp/diagram.png"],
        )

    cmd = captured_cmds[0]
    assert cmd.count("--image") == 1
    assert "/tmp/diagram.png" in cmd


def test_gemini_cli_image_flags_position(mock_proc_factory):
    """--image 플래그는 --output-format 이전에 위치해야 한다."""
    from app.services.llm.gemini_cli import _call_gemini_sync

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_cmds: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_gemini_sync(
            system_prompt="system",
            user_message="explain",
            file_paths=["/tmp/img.webp"],
        )

    cmd = captured_cmds[0]
    image_idx = cmd.index("--image")
    output_idx = cmd.index("--output-format")
    assert image_idx < output_idx


# ───────────────────────────────────────────────
# 통합: Provider → CLI file_paths 전달
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claude_provider_passes_file_paths_to_cli(mock_proc_factory):
    """ClaudeCliProvider.stream_generate → _call_claude_sync에 file_paths 전달."""
    from app.services.llm.claude_cli import ClaudeCliProvider

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    captured_kwargs: list[dict] = []

    original_call = __import__("app.services.cli_service", fromlist=["_call_claude_sync"])._call_claude_sync

    def fake_sync(system_prompt, user_message, on_line=None, **kwargs):
        captured_kwargs.append(kwargs)
        return ""

    with patch("app.services.cli_service._call_claude_sync", side_effect=fake_sync):
        provider = ClaudeCliProvider()
        await provider.stream_generate(
            system_prompt="system",
            user_message="hello",
            file_paths=["/tmp/a.jpg"],
        )

    assert any("file_paths" in kw and "/tmp/a.jpg" in kw["file_paths"] for kw in captured_kwargs)


@pytest.mark.asyncio
async def test_gemini_provider_passes_file_paths_to_cli(mock_proc_factory):
    """GeminiCliProvider.stream_generate → _call_gemini_sync에 file_paths 전달."""
    from app.services.llm.gemini_cli import GeminiCliProvider

    captured_kwargs: list[dict] = []

    def fake_sync(system_prompt, user_message, on_line=None, **kwargs):
        captured_kwargs.append(kwargs)
        return ""

    with patch("app.services.llm.gemini_cli._call_gemini_sync", side_effect=fake_sync):
        provider = GeminiCliProvider()
        await provider.stream_generate(
            system_prompt="system",
            user_message="describe",
            file_paths=["/tmp/b.png"],
        )

    assert any("file_paths" in kw and "/tmp/b.png" in kw["file_paths"] for kw in captured_kwargs)
