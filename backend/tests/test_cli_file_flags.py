"""Phase 3 CLI 파일 플래그 TDD 테스트

CLI-01: LLMProvider base interface file_paths 파라미터
CLI-02a: Claude CLI _call_claude_sync → --file 플래그
CLI-02b: Gemini CLI _call_gemini_sync → --image 플래그
"""

import os
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


def test_claude_cli_copies_files_to_tmp_and_includes_in_prompt(mock_proc_factory, tmp_path):
    """file_paths 전달 시 /tmp에 복사 후 복사된 경로가 프롬프트에 포함되어야 한다."""
    import shutil
    from app.services.cli_service import _call_claude_sync

    # 실제 파일 생성
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"fake-image")

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
            file_paths=[str(src)],
        )

    cmd = captured_cmds[0]
    assert "--file" not in cmd
    p_idx = cmd.index("-p")
    prompt_text = cmd[p_idx + 1]
    # 원본 경로 대신 /tmp 아래 복사된 경로가 포함되어야 함
    assert "photo.jpg" in prompt_text
    assert prompt_text.find("/tmp/") != -1 or "coworker_" in prompt_text


def test_claude_cli_no_file_ref_when_empty(mock_proc_factory):
    """file_paths=[] 시 프롬프트에 ATTACHED FILES 섹션이 없어야 한다."""
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

    cmd = captured_cmds[0]
    p_idx = cmd.index("-p")
    assert "ATTACHED FILES" not in cmd[p_idx + 1]


def test_claude_cli_no_file_ref_when_not_provided(mock_proc_factory):
    """file_paths 미전달 시 프롬프트에 ATTACHED FILES 섹션이 없어야 한다."""
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

    cmd = captured_cmds[0]
    p_idx = cmd.index("-p")
    assert "ATTACHED FILES" not in cmd[p_idx + 1]


def test_claude_cli_no_file_flag_always(mock_proc_factory, tmp_path):
    """파일 첨부 여부에 관계없이 --file 플래그는 절대 사용하지 않아야 한다."""
    from app.services.cli_service import _call_claude_sync

    src = tmp_path / "img.jpg"
    src.write_bytes(b"x")

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
            file_paths=[str(src)],
        )

    assert "--file" not in captured_cmds[0]


def test_claude_cli_tmp_dir_cleaned_up_after_call(mock_proc_factory, tmp_path):
    """CLI 호출 완료 후 /tmp 임시 디렉토리가 삭제되어야 한다."""
    from app.services.cli_service import _call_claude_sync

    src = tmp_path / "report.pdf"
    src.write_bytes(b"pdf-content")

    mock_proc = mock_proc_factory(stdout_lines=[], returncode=0)
    created_tmp_dirs: list[str] = []

    original_popen = subprocess.Popen

    def fake_popen(cmd, **kwargs):
        # -p 다음 프롬프트에서 /tmp/coworker_ 경로 추출
        p_idx = cmd.index("-p")
        prompt = cmd[p_idx + 1]
        for part in prompt.split("\n"):
            part = part.strip("- ").strip()
            if "/tmp/coworker_" in part:
                d = os.path.dirname(part)
                if d not in created_tmp_dirs:
                    created_tmp_dirs.append(d)
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _call_claude_sync(
            system_prompt="system",
            user_message="analyze",
            output_json=True,
            file_paths=[str(src)],
        )

    # 임시 디렉토리가 정리되었는지 확인
    for d in created_tmp_dirs:
        assert not os.path.exists(d), f"임시 디렉토리가 남아있음: {d}"


# ───────────────────────────────────────────────
# CLI-02b: Gemini CLI 파일 경로 프롬프트 포함 방식
# (Gemini CLI는 --image 플래그 미지원 → 프롬프트에 파일 경로 삽입)
# ───────────────────────────────────────────────


def test_gemini_cli_includes_file_paths_in_prompt(mock_proc_factory):
    """file_paths 전달 시 프롬프트(-p 인수)에 파일 경로가 포함되어야 한다."""
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
    # --image 플래그 없어야 함
    assert "--image" not in cmd
    # -p 다음 프롬프트 문자열에 파일 경로 포함 여부 확인
    p_idx = cmd.index("-p")
    prompt_text = cmd[p_idx + 1]
    assert "/tmp/photo.jpg" in prompt_text
    assert "/tmp/chart.png" in prompt_text


def test_gemini_cli_no_file_ref_when_empty(mock_proc_factory):
    """file_paths=[] 시 프롬프트에 ATTACHED FILES 섹션이 없어야 한다."""
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

    cmd = captured_cmds[0]
    p_idx = cmd.index("-p")
    prompt_text = cmd[p_idx + 1]
    assert "ATTACHED FILES" not in prompt_text


def test_gemini_cli_no_file_ref_when_not_provided(mock_proc_factory):
    """file_paths 미전달 시 프롬프트에 ATTACHED FILES 섹션이 없어야 한다."""
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

    cmd = captured_cmds[0]
    p_idx = cmd.index("-p")
    prompt_text = cmd[p_idx + 1]
    assert "ATTACHED FILES" not in prompt_text


def test_gemini_cli_single_file_in_prompt(mock_proc_factory):
    """단일 파일 전달 시 프롬프트에 해당 경로가 포함되어야 한다."""
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
    assert "--image" not in cmd
    p_idx = cmd.index("-p")
    assert "/tmp/diagram.png" in cmd[p_idx + 1]


def test_gemini_cli_no_image_flag_always(mock_proc_factory):
    """파일 첨부 여부에 관계없이 --image 플래그는 절대 사용하지 않아야 한다."""
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

    assert "--image" not in captured_cmds[0]


def test_gemini_cli_adds_include_directories_for_file_paths(mock_proc_factory):
    """file_paths 전달 시 --include-directories 플래그로 해당 폴더가 추가되어야 한다."""
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
    assert "--include-directories" in cmd
    inc_idx = cmd.index("--include-directories")
    assert cmd[inc_idx + 1] == "/tmp"


def test_gemini_cli_no_include_directories_when_no_files(mock_proc_factory):
    """file_paths 없을 때 --include-directories 플래그가 없어야 한다."""
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

    assert "--include-directories" not in captured_cmds[0]


def test_gemini_cli_deduplicates_include_directories(mock_proc_factory):
    """같은 폴더의 파일이 여럿이면 --include-directories는 중복 없이 1번만 추가되어야 한다."""
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
            file_paths=["/tmp/a.jpg", "/tmp/b.png", "/tmp/c.webp"],
        )

    cmd = captured_cmds[0]
    assert cmd.count("--include-directories") == 1


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
