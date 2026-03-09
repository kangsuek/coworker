"""파일 업로드 임시 저장 서비스 (UPLOAD-02).

핵심 구조:
- save_upload(): UploadFile을 UUID 기반 파일명으로 upload_dir에 저장
- get_upload_path(): file_id로 저장 경로 반환
- cleanup_expired_uploads(): TTL 초과 파일 삭제
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# 모듈 레벨 상수 (엔드포인트에서 patch 가능하도록 분리)
UPLOAD_DIR = Path(settings.upload_dir)

# LLM CLI에서 처리 가능한 허용 확장자
ALLOWED_TEXT_EXTENSIONS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".log",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css",
    ".scss", ".sass", ".json", ".yaml", ".yml", ".toml", ".xml",
    ".env", ".sh", ".bash", ".zsh", ".sql", ".graphql", ".proto",
    ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".kt", ".r", ".scala", ".dart",
    ".lua", ".vim", ".dockerfile", ".makefile", ".gitignore",
})

ALLOWED_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp",
})

ALLOWED_EXTENSIONS: frozenset[str] = ALLOWED_TEXT_EXTENSIONS | ALLOWED_BINARY_EXTENSIONS

# 확장자가 없거나 이름 자체가 확장자인 파일 (예: .gitignore, .env, Makefile)
_DOTFILE_ALLOWLIST: frozenset[str] = frozenset({
    ".gitignore", ".env", ".dockerfile",
})

_BARE_NAME_ALLOWLIST: frozenset[str] = frozenset({
    "makefile", "dockerfile",
})


def _resolve_extension(filename: str) -> str:
    """파일명에서 허용 여부 판단용 확장자를 추출한다.

    - '.gitignore' → '.gitignore'  (점으로 시작하는 파일)
    - 'Makefile'   → 'makefile'    (확장자 없는 특수 파일)
    - 'main.py'    → '.py'
    - 'noext'      → ''            (허용 안 함)
    """
    name_lower = filename.lower()
    # 점으로 시작하는 숨김 파일 (예: .gitignore, .env)
    if filename.startswith(".") and "." not in filename[1:]:
        return filename.lower()
    # 확장자 없는 특수 파일 (Makefile, Dockerfile)
    if "." not in filename:
        return name_lower
    return Path(filename).suffix.lower()


def _is_allowed(filename: str) -> bool:
    """파일명의 확장자가 허용 목록에 있는지 확인."""
    ext = _resolve_extension(filename)
    # 빈 확장자 (noext 파일) → allowlist 직접 확인
    if not ext:
        return False
    if ext in _DOTFILE_ALLOWLIST:
        return True
    name_lower = filename.lower()
    if name_lower in _BARE_NAME_ALLOWLIST:
        return True
    return ext in ALLOWED_EXTENSIONS


async def save_upload(file, upload_dir: Path, max_size_bytes: int) -> dict:
    """UploadFile(또는 FakeUploadFile)을 upload_dir에 저장.

    Args:
        file: filename, size(optional), read() 메서드를 가진 파일 객체
        upload_dir: 저장 디렉토리
        max_size_bytes: 최대 허용 크기 (바이트)

    Returns:
        {"file_id": str, "filename": str, "path": str, "size": int}

    Raises:
        ValueError: 파일 크기 초과 또는 허용되지 않는 확장자
    """
    filename = file.filename or ""

    # 확장자 검증
    if not _is_allowed(filename):
        raise ValueError(f"허용되지 않는 확장자: {filename}")

    # 내용 읽기
    content: bytes = await file.read()

    # 크기 검증
    if len(content) > max_size_bytes:
        raise ValueError(
            f"파일 크기 초과: {len(content)} bytes > {max_size_bytes} bytes ({filename})"
        )

    # UUID 기반 파일명 생성 (원본 확장자 보존)
    file_id = str(uuid.uuid4())
    ext = _resolve_extension(filename)
    # 점으로 시작하는 확장자가 아닌 경우 점 보장
    if ext and not ext.startswith("."):
        save_ext = f".{ext}"
    else:
        save_ext = ext

    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{file_id}{save_ext}"
    dest.write_bytes(content)

    logger.info("파일 저장: file_id=%s, filename=%s, size=%d", file_id, filename, len(content))

    return {
        "file_id": file_id,
        "filename": filename,
        "path": str(dest),
        "size": len(content),
    }


def get_upload_path(file_id: str, upload_dir: Path) -> Path | None:
    """file_id로 저장된 파일 경로를 반환.

    보안: file_id에 경로 구분자(/,\\) 또는 '..'가 있으면 None 반환.

    Returns:
        Path if file exists, None otherwise
    """
    # 경로 traversal 방지
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        logger.warning("경로 traversal 시도 차단: file_id=%s", file_id)
        return None

    # upload_dir 내에서 file_id로 시작하는 파일 검색
    for candidate in upload_dir.glob(f"{file_id}.*"):
        if candidate.is_file():
            return candidate
    # 확장자 없는 파일 (dotfile 등)
    candidate = upload_dir / file_id
    if candidate.is_file():
        return candidate
    return None


def cleanup_expired_uploads(upload_dir: Path, ttl_seconds: int) -> None:
    """upload_dir 내에서 TTL 초과 파일을 삭제.

    upload_dir가 존재하지 않으면 아무것도 하지 않음.
    """
    if not upload_dir.exists():
        return

    now = time.time()
    deleted = 0
    for f in upload_dir.iterdir():
        if not f.is_file():
            continue
        age = now - f.stat().st_mtime
        if age > ttl_seconds:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                logger.warning("임시 파일 삭제 실패: %s", f)

    if deleted:
        logger.info("만료 파일 %d개 삭제: upload_dir=%s", deleted, upload_dir)
