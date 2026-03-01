"""세션 CRUD 서비스."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import db as models


async def create_session(db: AsyncSession) -> models.Session:
    """새 세션 생성."""
    sess = models.Session()
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_session(db: AsyncSession, session_id: str) -> models.Session | None:
    """세션 ID로 조회. 없으면 None."""
    return await db.get(models.Session, session_id)


async def list_sessions(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> list[models.Session]:
    """전체 세션 목록 (최신순, limit/offset 페이징)."""
    result = await db.execute(
        select(models.Session)
        .order_by(models.Session.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_session_with_messages(db: AsyncSession, session_id: str) -> models.Session | None:
    """세션 + user_messages eager load."""
    result = await db.execute(
        select(models.Session)
        .options(selectinload(models.Session.user_messages))
        .where(models.Session.id == session_id)
    )
    return result.scalar_one_or_none()


async def create_user_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    mode: str | None = None,
) -> models.UserMessage:
    """유저/리더 메시지 생성. user 역할인 경우 세션 제목 자동 설정."""
    if role == "user":
        session = await db.get(models.Session, session_id)
        if session is not None and session.title is None:
            session.title = content[:30] + ("…" if len(content) > 30 else "")

    msg = models.UserMessage(
        session_id=session_id,
        role=role,
        content=content,
        mode=mode,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def create_run(db: AsyncSession, session_id: str, user_message_id: str) -> models.Run:
    """Run 생성 (초기 status='queued')."""
    run = models.Run(
        session_id=session_id,
        user_message_id=user_message_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def update_run_status(
    db: AsyncSession, run_id: str, status: str, **fields
) -> models.Run | None:
    """Run 상태 및 필드 업데이트."""
    run = await db.get(models.Run, run_id)
    if run is None:
        return None
    run.status = status
    for key, value in fields.items():
        if hasattr(run, key):
            setattr(run, key, value)
    await db.commit()
    await db.refresh(run)
    return run
