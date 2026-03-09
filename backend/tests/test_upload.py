"""Phase 1 파일 업로드 기능 TDD 테스트

UPLOAD-01: config 설정값
UPLOAD-02: upload_service (저장 / 경로 조회 / 만료 정리)
UPLOAD-03: POST /api/upload 엔드포인트
"""

import io
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ───────────────────────────────────────────────
# UPLOAD-01: config.py 설정값 검증
# ───────────────────────────────────────────────


def test_config_upload_dir_default():
    """upload_dir 기본값이 존재해야 한다."""
    from app.config import settings
    assert hasattr(settings, "upload_dir")
    assert settings.upload_dir != ""


def test_config_upload_max_size_mb_default():
    """upload_max_size_mb 기본값이 양수여야 한다."""
    from app.config import settings
    assert hasattr(settings, "upload_max_size_mb")
    assert settings.upload_max_size_mb > 0


def test_config_upload_ttl_seconds_default():
    """upload_ttl_seconds 기본값이 양수여야 한다."""
    from app.config import settings
    assert hasattr(settings, "upload_ttl_seconds")
    assert settings.upload_ttl_seconds > 0


# ───────────────────────────────────────────────
# UPLOAD-02: upload_service 단위 테스트
# ───────────────────────────────────────────────


@pytest.fixture
def upload_dir(tmp_path):
    """테스트용 임시 업로드 디렉토리."""
    d = tmp_path / "uploads"
    d.mkdir()
    return d


@pytest.fixture
def max_size_bytes():
    return 10 * 1024 * 1024  # 10 MB


class FakeUploadFile:
    """httpx UploadFile 대신 테스트에서 사용하는 가짜 파일 객체."""

    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content
        self.size = len(content)

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
async def test_save_upload_returns_file_id(upload_dir, max_size_bytes):
    """save_upload → file_id, filename, path, size 포함 dict 반환."""
    from app.services.upload_service import save_upload

    fake = FakeUploadFile("photo.png", b"fakepngdata")
    result = await save_upload(fake, upload_dir, max_size_bytes)

    assert "file_id" in result
    assert result["filename"] == "photo.png"
    assert "path" in result
    assert result["size"] == len(b"fakepngdata")


@pytest.mark.asyncio
async def test_save_upload_preserves_extension(upload_dir, max_size_bytes):
    """저장된 파일명은 UUID + 원본 확장자 형식이어야 한다."""
    from app.services.upload_service import save_upload

    fake = FakeUploadFile("report.pdf", b"%PDF-content")
    result = await save_upload(fake, upload_dir, max_size_bytes)

    saved_path = Path(result["path"])
    assert saved_path.exists()
    assert saved_path.suffix == ".pdf"


@pytest.mark.asyncio
async def test_save_upload_file_exists_on_disk(upload_dir, max_size_bytes):
    """save_upload 후 파일이 실제로 디스크에 저장되어야 한다."""
    from app.services.upload_service import save_upload

    content = b"hello world code"
    fake = FakeUploadFile("main.py", content)
    result = await save_upload(fake, upload_dir, max_size_bytes)

    saved = Path(result["path"])
    assert saved.exists()
    assert saved.read_bytes() == content


@pytest.mark.asyncio
async def test_save_upload_raises_on_oversized_file(upload_dir):
    """파일 크기가 max_size_bytes 초과 시 ValueError 발생."""
    from app.services.upload_service import save_upload

    small_limit = 10  # 10 bytes
    fake = FakeUploadFile("big.txt", b"x" * 11)
    with pytest.raises(ValueError, match="파일 크기"):
        await save_upload(fake, upload_dir, small_limit)


@pytest.mark.asyncio
async def test_save_upload_raises_on_disallowed_extension(upload_dir, max_size_bytes):
    """허용되지 않은 확장자 파일 시 ValueError 발생."""
    from app.services.upload_service import save_upload

    fake = FakeUploadFile("malware.exe", b"MZ...")
    with pytest.raises(ValueError, match="허용되지 않는 확장자"):
        await save_upload(fake, upload_dir, max_size_bytes)


@pytest.mark.asyncio
async def test_save_upload_raises_on_no_extension(upload_dir, max_size_bytes):
    """허용 목록에 없는 확장자 없는 파일명도 거부해야 한다."""
    from app.services.upload_service import save_upload

    fake = FakeUploadFile("unknownfile", b"data")
    with pytest.raises(ValueError, match="허용되지 않는 확장자"):
        await save_upload(fake, upload_dir, max_size_bytes)


@pytest.mark.asyncio
async def test_save_upload_dotfile_with_allowed_name(upload_dir, max_size_bytes):
    """'.gitignore' 같이 확장자가 이름 자체인 파일은 허용되어야 한다."""
    from app.services.upload_service import save_upload

    fake = FakeUploadFile(".gitignore", b"*.pyc")
    result = await save_upload(fake, upload_dir, max_size_bytes)
    assert Path(result["path"]).exists()


def test_get_upload_path_returns_path(upload_dir):
    """get_upload_path → 존재하는 파일의 Path 반환."""
    from app.services.upload_service import get_upload_path

    # 파일 직접 생성
    file_id = "abc123"
    f = upload_dir / f"{file_id}.png"
    f.write_bytes(b"data")

    result = get_upload_path(file_id, upload_dir)
    assert result is not None
    assert result == f


def test_get_upload_path_returns_none_for_unknown(upload_dir):
    """get_upload_path → 존재하지 않는 file_id → None 반환."""
    from app.services.upload_service import get_upload_path

    result = get_upload_path("nonexistent-id", upload_dir)
    assert result is None


def test_get_upload_path_rejects_path_traversal(upload_dir):
    """경로 traversal 시도 시 None 반환 (보안)."""
    from app.services.upload_service import get_upload_path

    result = get_upload_path("../../etc/passwd", upload_dir)
    assert result is None


def test_cleanup_expired_uploads_deletes_old_files(upload_dir):
    """TTL 초과 파일은 삭제되어야 한다."""
    from app.services.upload_service import cleanup_expired_uploads

    old_file = upload_dir / "old.txt"
    old_file.write_text("old content")

    # 수정 시간을 과거로 설정 (TTL=1초, 파일은 10초 전 생성된 것처럼)
    old_time = time.time() - 10
    import os
    os.utime(old_file, (old_time, old_time))

    cleanup_expired_uploads(upload_dir, ttl_seconds=1)
    assert not old_file.exists()


def test_cleanup_expired_uploads_keeps_recent_files(upload_dir):
    """TTL 이내 파일은 유지되어야 한다."""
    from app.services.upload_service import cleanup_expired_uploads

    recent_file = upload_dir / "recent.png"
    recent_file.write_bytes(b"new image")

    cleanup_expired_uploads(upload_dir, ttl_seconds=3600)
    assert recent_file.exists()


def test_cleanup_expired_uploads_empty_dir(upload_dir):
    """빈 디렉토리에서 오류 없이 실행되어야 한다."""
    from app.services.upload_service import cleanup_expired_uploads

    cleanup_expired_uploads(upload_dir, ttl_seconds=1)  # 예외 없이 통과


# ───────────────────────────────────────────────
# UPLOAD-03: POST /api/upload 엔드포인트 테스트
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_endpoint_returns_file_id(client, tmp_path):
    """POST /api/upload 이미지 → 200, file_id 반환."""
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads") as _:
        (tmp_path / "uploads").mkdir(exist_ok=True)
        response = await client.post(
            "/api/upload",
            files=[("files", ("photo.png", io.BytesIO(b"fakepng"), "image/png"))],
        )
    assert response.status_code == 200
    data = response.json()
    assert "uploaded" in data
    assert len(data["uploaded"]) == 1
    assert "file_id" in data["uploaded"][0]
    assert data["uploaded"][0]["filename"] == "photo.png"


@pytest.mark.asyncio
async def test_upload_endpoint_text_file(client, tmp_path):
    """POST /api/upload 텍스트 파일 → 200."""
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads") as _:
        (tmp_path / "uploads").mkdir(exist_ok=True)
        response = await client.post(
            "/api/upload",
            files=[("files", ("main.py", io.BytesIO(b"print('hello')"), "text/plain"))],
        )
    assert response.status_code == 200
    assert len(response.json()["uploaded"]) == 1


@pytest.mark.asyncio
async def test_upload_endpoint_multiple_files(client, tmp_path):
    """POST /api/upload 복수 파일 → 모두 반환."""
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads") as _:
        (tmp_path / "uploads").mkdir(exist_ok=True)
        response = await client.post(
            "/api/upload",
            files=[
                ("files", ("a.txt", io.BytesIO(b"aaa"), "text/plain")),
                ("files", ("b.md", io.BytesIO(b"bbb"), "text/markdown")),
            ],
        )
    assert response.status_code == 200
    assert len(response.json()["uploaded"]) == 2


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_disallowed_extension(client, tmp_path):
    """허용되지 않는 확장자 → 422."""
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads") as _:
        (tmp_path / "uploads").mkdir(exist_ok=True)
        response = await client.post(
            "/api/upload",
            files=[("files", ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream"))],
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_oversized_file(client, tmp_path):
    """max_size_mb 초과 파일 → 413."""
    oversized = b"x" * (11 * 1024 * 1024)  # 11 MB
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads"):
        (tmp_path / "uploads").mkdir(exist_ok=True)
        with patch("app.routers.chat.MAX_UPLOAD_SIZE_BYTES", 1024):  # 1 KB로 축소
            response = await client.post(
                "/api/upload",
                files=[("files", ("big.txt", io.BytesIO(oversized), "text/plain"))],
            )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_endpoint_no_files_returns_422(client):
    """파일 없이 POST → 422."""
    response = await client.post("/api/upload", files=[])
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_endpoint_partial_reject(client, tmp_path):
    """허용 파일 + 비허용 파일 혼합 → 422 (전체 거부)."""
    with patch("app.services.upload_service.UPLOAD_DIR", tmp_path / "uploads"):
        (tmp_path / "uploads").mkdir(exist_ok=True)
        response = await client.post(
            "/api/upload",
            files=[
                ("files", ("ok.txt", io.BytesIO(b"good"), "text/plain")),
                ("files", ("bad.zip", io.BytesIO(b"zip"), "application/zip")),
            ],
        )
    assert response.status_code == 422
