"""Phase 2 파일 첨부 연동 TDD 테스트

ATTACH-01: ChatRequest.file_ids 스키마 확장
ATTACH-02: ReaderAgent _split_files / _inject_text_files / process_message 연동
ATTACH-03: POST /api/chat file_ids → file_paths 변환 및 ReaderAgent 전달
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ───────────────────────────────────────────────
# ATTACH-01: ChatRequest 스키마
# ───────────────────────────────────────────────


def test_chat_request_accepts_file_ids():
    """ChatRequest가 file_ids 필드를 수용해야 한다."""
    from app.models.schemas import ChatRequest

    req = ChatRequest(message="hello", file_ids=["id-1", "id-2"])
    assert req.file_ids == ["id-1", "id-2"]


def test_chat_request_file_ids_defaults_to_empty():
    """file_ids 미전달 시 빈 리스트로 기본값 설정."""
    from app.models.schemas import ChatRequest

    req = ChatRequest(message="hello")
    assert req.file_ids == []


def test_chat_request_backward_compatible(client):
    """file_ids 없이도 POST /api/chat 정상 동작 (하위 호환)."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        import asyncio
        resp = asyncio.get_event_loop().run_until_complete(
            client.post("/api/chat", json={"message": "테스트"})
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_request_with_file_ids_returns_200(client):
    """file_ids 포함 POST /api/chat → 200 반환."""
    with patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock):
        resp = await client.post(
            "/api/chat",
            json={"message": "파일 분석해줘", "file_ids": ["uuid-1", "uuid-2"]},
        )
    assert resp.status_code == 200
    assert "run_id" in resp.json()


# ───────────────────────────────────────────────
# ATTACH-02: _split_files 함수
# ───────────────────────────────────────────────


def test_split_files_empty_list():
    """빈 리스트 → native, text_files 모두 빈 리스트."""
    from app.agents.reader import _split_files

    native, text_files = _split_files([])
    assert native == []
    assert text_files == []


def test_split_files_image_goes_to_native():
    """이미지 파일(.jpg .png .gif .webp) → native 버킷."""
    from app.agents.reader import _split_files

    paths = ["/tmp/a.jpg", "/tmp/b.png", "/tmp/c.gif", "/tmp/d.webp"]
    native, text_files = _split_files(paths)
    assert len(native) == 4
    assert text_files == []


def test_split_files_pdf_goes_to_native():
    """PDF → native 버킷."""
    from app.agents.reader import _split_files

    native, text_files = _split_files(["/tmp/report.pdf"])
    assert native == ["/tmp/report.pdf"]
    assert text_files == []


def test_split_files_text_code_goes_to_text():
    """텍스트/코드 파일 → text_files 버킷."""
    from app.agents.reader import _split_files

    paths = ["/tmp/main.py", "/tmp/readme.md", "/tmp/data.json"]
    native, text_files = _split_files(paths)
    assert native == []
    assert len(text_files) == 3


def test_split_files_mixed():
    """이미지 + 텍스트 혼합 → 각 버킷에 분리."""
    from app.agents.reader import _split_files

    paths = ["/tmp/photo.jpeg", "/tmp/code.ts", "/tmp/doc.pdf", "/tmp/readme.txt"]
    native, text_files = _split_files(paths)
    assert set(native) == {"/tmp/photo.jpeg", "/tmp/doc.pdf"}
    assert set(text_files) == {"/tmp/code.ts", "/tmp/readme.txt"}


def test_split_files_case_insensitive():
    """확장자 대소문자 구분 없이 처리."""
    from app.agents.reader import _split_files

    native, text_files = _split_files(["/tmp/PHOTO.JPG", "/tmp/DOC.PDF"])
    assert len(native) == 2
    assert text_files == []


# ───────────────────────────────────────────────
# ATTACH-02: _inject_text_files 함수
# ───────────────────────────────────────────────


def test_inject_text_files_no_files_returns_original(tmp_path):
    """텍스트 파일 없으면 원본 메시지 그대로 반환."""
    from app.agents.reader import _inject_text_files

    result = _inject_text_files("원본 메시지", [])
    assert result == "원본 메시지"


def test_inject_text_files_single_file(tmp_path):
    """단일 파일 내용이 메시지에 삽입되어야 한다."""
    from app.agents.reader import _inject_text_files

    f = tmp_path / "hello.py"
    f.write_text("print('hello')", encoding="utf-8")

    result = _inject_text_files("코드 분석해줘", [str(f)])
    assert "코드 분석해줘" in result
    assert "hello.py" in result
    assert "print('hello')" in result


def test_inject_text_files_multiple_files(tmp_path):
    """복수 파일 모두 삽입되어야 한다."""
    from app.agents.reader import _inject_text_files

    f1 = tmp_path / "a.py"
    f1.write_text("# file a", encoding="utf-8")
    f2 = tmp_path / "b.md"
    f2.write_text("# Readme", encoding="utf-8")

    result = _inject_text_files("분석해줘", [str(f1), str(f2)])
    assert "a.py" in result
    assert "b.md" in result
    assert "# file a" in result
    assert "# Readme" in result


def test_inject_text_files_truncates_long_content(tmp_path):
    """20000자 초과 파일 내용은 잘라야 한다."""
    from app.agents.reader import _inject_text_files

    f = tmp_path / "big.txt"
    f.write_text("x" * 25000, encoding="utf-8")

    result = _inject_text_files("요청", [str(f)])
    # 원본 25000자가 아닌 20000자 + 생략 표시가 있어야 함
    assert "x" * 20000 in result
    assert "x" * 25000 not in result
    assert "생략" in result or "..." in result


def test_inject_text_files_shows_filename(tmp_path):
    """삽입된 내용에 파일명이 표시되어야 한다."""
    from app.agents.reader import _inject_text_files

    f = tmp_path / "config.yaml"
    f.write_text("key: value", encoding="utf-8")

    result = _inject_text_files("설정 확인", [str(f)])
    assert "config.yaml" in result


def test_inject_text_files_handles_missing_file(tmp_path):
    """존재하지 않는 파일은 건너뛰고 오류 없이 진행."""
    from app.agents.reader import _inject_text_files

    result = _inject_text_files("요청", ["/nonexistent/missing.txt"])
    # 오류 없이 반환, 원본 메시지는 유지
    assert "요청" in result


# ───────────────────────────────────────────────
# ATTACH-02: process_message file_paths 연동
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_message_text_file_injected_into_prompt(db, tmp_path):
    """텍스트 파일 → 프롬프트에 내용 삽입 후 CLI 호출."""
    from app.agents.reader import ReaderAgent
    from app.services.session_service import create_run, create_session, create_user_message

    # 텍스트 파일 생성
    code_file = tmp_path / "app.py"
    code_file.write_text("def hello(): pass", encoding="utf-8")

    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "코드 분석")
    run = await create_run(db, sess.id, msg.id)

    captured_prompts: list[str] = []

    async def mock_stream_generate(system_prompt, user_message, **kwargs):
        captured_prompts.append(user_message)
        return "solo 응답"

    with (
        patch("app.agents.reader.classify_message", new_callable=AsyncMock) as mock_classify,
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch("app.agents.reader.get_recent_messages", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_all_memories", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_custom_roles", new_callable=AsyncMock, return_value={}),
        patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", side_effect=mock_stream_generate),
    ):
        from app.models.schemas import ClassificationResult
        mock_classify.return_value = ClassificationResult(mode="solo", reason="simple", agents=[])

        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "코드 분석", run.id, file_paths=[str(code_file)])

    # 텍스트 파일 내용이 프롬프트에 포함되어야 함
    assert any("def hello(): pass" in p for p in captured_prompts)
    assert any("app.py" in p for p in captured_prompts)


@pytest.mark.asyncio
async def test_process_message_image_passed_as_native(db, tmp_path):
    """이미지 파일 → file_paths kwarg로 CLI에 전달되어야 한다."""
    from app.agents.reader import ReaderAgent
    from app.services.session_service import create_run, create_session, create_user_message

    # 이미지 파일 (내용은 중요하지 않음, 경로만 사용)
    img_file = tmp_path / "photo.png"
    img_file.write_bytes(b"fakepng")

    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "이미지 설명")
    run = await create_run(db, sess.id, msg.id)

    captured_kwargs: list[dict] = []

    async def mock_stream_generate(system_prompt, user_message, **kwargs):
        captured_kwargs.append(kwargs)
        return "이미지 응답"

    with (
        patch("app.agents.reader.classify_message", new_callable=AsyncMock) as mock_classify,
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch("app.agents.reader.get_recent_messages", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_all_memories", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_custom_roles", new_callable=AsyncMock, return_value={}),
        patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", side_effect=mock_stream_generate),
    ):
        from app.models.schemas import ClassificationResult
        mock_classify.return_value = ClassificationResult(mode="solo", reason="simple", agents=[])

        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "이미지 설명", run.id, file_paths=[str(img_file)])

    # native_files이 CLI kwargs로 전달되어야 함
    assert any("file_paths" in kw and str(img_file) in kw["file_paths"] for kw in captured_kwargs)


@pytest.mark.asyncio
async def test_process_message_no_files_unchanged(db):
    """file_paths 없으면 기존 동작과 동일해야 한다."""
    from app.agents.reader import ReaderAgent
    from app.services.session_service import create_run, create_session, create_user_message

    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "질문")
    run = await create_run(db, sess.id, msg.id)

    with (
        patch("app.agents.reader.classify_message", new_callable=AsyncMock) as mock_classify,
        patch("app.agents.reader.update_run_status", new_callable=AsyncMock),
        patch("app.agents.reader.create_user_message", new_callable=AsyncMock),
        patch("app.agents.reader.get_recent_messages", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_all_memories", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.reader.get_custom_roles", new_callable=AsyncMock, return_value={}),
        patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", new_callable=AsyncMock, return_value="응답") as mock_gen,
    ):
        from app.models.schemas import ClassificationResult
        mock_classify.return_value = ClassificationResult(mode="solo", reason="simple", agents=[])

        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "질문", run.id)  # file_paths 미전달

    mock_gen.assert_called_once()


# ───────────────────────────────────────────────
# ATTACH-03: chat.py file_ids → file_paths 변환
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_with_file_ids_resolves_paths(client, tmp_path):
    """POST /api/chat file_ids → _run_reader_agent에 file_paths 전달."""
    # 업로드된 것처럼 파일 생성
    fake_file = tmp_path / "abc123.py"
    fake_file.write_text("code", encoding="utf-8")

    captured_args: list = []

    async def mock_run_reader_agent(*args, **kwargs):
        captured_args.extend(args)
        captured_args.append(kwargs)

    with (
        patch("app.routers.chat._run_reader_agent", side_effect=mock_run_reader_agent),
        patch("app.routers.chat.get_upload_path", return_value=fake_file),
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "분석", "file_ids": ["abc123"]},
        )

    assert resp.status_code == 200
    # file_paths가 전달되었는지 확인
    assert any(str(fake_file) in str(a) for a in captured_args)


@pytest.mark.asyncio
async def test_chat_unknown_file_ids_are_skipped(client):
    """존재하지 않는 file_id는 건너뛰고 정상 처리."""
    with (
        patch("app.routers.chat._run_reader_agent", new_callable=AsyncMock),
        patch("app.routers.chat.get_upload_path", return_value=None),  # 파일 없음
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "질문", "file_ids": ["nonexistent-id"]},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_without_file_ids_calls_with_empty_paths(client):
    """file_ids 없으면 _run_reader_agent에 빈 file_paths 전달."""
    captured: list = []

    async def mock_run(*args, **kwargs):
        captured.append(kwargs.get("file_paths", args[3] if len(args) > 3 else []))

    with patch("app.routers.chat._run_reader_agent", side_effect=mock_run):
        resp = await client.post("/api/chat", json={"message": "질문"})

    assert resp.status_code == 200
    assert captured[0] == []
