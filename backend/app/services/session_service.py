"""세션 CRUD 서비스."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import db as models


async def create_session(
    db: AsyncSession,
    llm_provider: str = "gemini-cli",
    llm_model: str | None = "gemini-3-flash-preview"
) -> models.Session:
    """새 세션 생성."""
    sess = models.Session(llm_provider=llm_provider, llm_model=llm_model)
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_session(db: AsyncSession, session_id: str) -> models.Session | None:
    """세션 ID로 조회. 없으면 None."""
    return await db.get(models.Session, session_id)


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    """세션 및 관련 runs, agent_messages, user_messages 삭제. 없으면 False."""
    session = await db.get(models.Session, session_id)
    if session is None:
        return False
    # FK 제약 순서: AgentMessage → Run → UserMessage → Session
    await db.execute(
        delete(models.AgentMessage).where(models.AgentMessage.session_id == session_id)
    )
    await db.execute(delete(models.Run).where(models.Run.session_id == session_id))
    await db.execute(delete(models.UserMessage).where(models.UserMessage.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return True


async def list_sessions(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> list[models.Session]:
    """전체 세션 목록 (최신순, limit/offset 페이징)."""
    result = await db.execute(
        select(models.Session)
        .order_by(models.Session.updated_at.desc())
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
    """유저/리더 메시지 생성. user 역할인 경우 세션 제목 자동 설정. 항상 updated_at 갱신."""
    session = await db.get(models.Session, session_id)
    if session is not None:
        # 메시지가 추가될 때마다 세션 updated_at 갱신 (최근 활동순 정렬 기준)
        session.updated_at = datetime.now(UTC)
        if role == "user" and session.title is None:
            from app.config import settings
            triggers = [t for t in [settings.team_trigger_header, settings.role_add_trigger, settings.memory_trigger] if t]
            if not any(content.startswith(t) for t in triggers):
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


async def update_session_title(db: AsyncSession, session_id: str, title: str) -> models.Session | None:
    """세션 제목 업데이트."""
    session = await db.get(models.Session, session_id)
    if session is None:
        return None
    session.title = title.strip() or None
    await db.commit()
    await db.refresh(session)
    return session


async def get_custom_roles(db: AsyncSession, session_id: str) -> dict[str, str]:
    """세션의 커스텀 역할 목록 반환. 없으면 빈 dict."""
    session = await db.get(models.Session, session_id)
    if session is None or not session.custom_roles:
        return {}
    try:
        return json.loads(session.custom_roles)
    except json.JSONDecodeError:
        return {}


async def add_custom_role(
    db: AsyncSession, session_id: str, role_name: str, prompt: str
) -> dict[str, str]:
    """세션에 커스텀 역할 추가 후 전체 커스텀 역할 dict 반환."""
    session = await db.get(models.Session, session_id)
    if session is None:
        return {}
    existing = {}
    if session.custom_roles:
        try:
            existing = json.loads(session.custom_roles)
        except json.JSONDecodeError:
            pass
    existing[role_name] = prompt
    session.custom_roles = json.dumps(existing, ensure_ascii=False)
    await db.commit()
    return existing


async def create_run(db: AsyncSession, session_id: str, user_message_id: str) -> models.Run:
    """Run 생성 (초기 status='queued')."""
    run = models.Run(
        session_id=session_id,
        user_message_id=user_message_id,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


_TERMINAL_STATUSES = {"done", "error", "cancelled"}


async def update_run_status(
    db: AsyncSession, run_id: str, status: str, **fields
) -> models.Run | None:
    """Run 상태 및 필드 업데이트."""
    run = await db.get(models.Run, run_id)
    if run is None:
        # TODO-06: 미존재 시에도 취소 목록 정리
        try:
            from app.services.cli_service import _cancelled_runs
            _cancelled_runs.discard(run_id)
        except Exception:
            pass
        return None
    # TODO-02: 이미 terminal 상태이면 업데이트 스킵 (race condition 방지)
    if run.status in _TERMINAL_STATUSES:
        try:
            from app.services.cli_service import _cancelled_runs
            _cancelled_runs.discard(run_id)
        except Exception:
            pass
        return run
    run.status = status
    for key, value in fields.items():
        if hasattr(run, key):
            setattr(run, key, value)
    await db.commit()
    await db.refresh(run)

    # 실시간 스트리밍 업데이트 전송
    try:
        from app.services.stream_service import stream_manager
        await stream_manager.broadcast(run_id, {
            "type": "status",
            "run_id": run_id,
            "status": status,
            "progress": run.progress,
            "mode": run.mode,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None
        })
    except Exception:
        pass

    # 종료 상태 도달 시 취소 목록에서 정리 (메모리 누수 방지)
    # "cancelled"는 제외: cancel 시그널이 살아 있어야 백그라운드 태스크가 신규 CLI 실행을 막을 수 있음
    # _cancelled_runs 정리는 process_message finally 블록에서 수행
    if status in ("done", "error"):
        try:
            from app.services.cli_service import _cancelled_runs
            _cancelled_runs.discard(run_id)
        except Exception:
            pass

    return run


async def get_recent_messages(
    db: AsyncSession,
    session_id: str,
    limit: int = 20,
    exclude_id: str | None = None,
) -> list[models.UserMessage]:
    """세션의 최근 메시지 목록 (시간순). 현재 메시지(exclude_id)는 제외."""
    stmt = select(models.UserMessage).where(models.UserMessage.session_id == session_id)
    if exclude_id:
        stmt = stmt.where(models.UserMessage.id != exclude_id)
    stmt = stmt.order_by(models.UserMessage.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    msgs = list(result.scalars().all())
    return list(reversed(msgs))  # 오래된 것이 앞으로


async def create_agent_message(
    db: AsyncSession,
    session_id: str,
    run_id: str,
    sender: str,
    role_preset: str,
) -> models.AgentMessage:
    """AgentMessage 레코드 생성 (초기 status='working')."""
    msg = models.AgentMessage(
        session_id=session_id,
        run_id=run_id,
        sender=sender,
        role_preset=role_preset,
        content="",
        status="working",
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # 실시간 스트리밍 업데이트 전송 (에이전트 생성)
    try:
        from app.services.stream_service import stream_manager
        await stream_manager.broadcast(run_id, {
            "type": "agent_message_created",
            "run_id": run_id,
            "agent_message": {
                "id": msg.id,
                "sender": msg.sender,
                "role_preset": msg.role_preset,
                "status": msg.status,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
        })
    except Exception:
        pass

    return msg


async def update_agent_message_content(
    db: AsyncSession, msg_id: str, content: str
) -> models.AgentMessage | None:
    """AgentMessage 내용 업데이트 (중간 출력 누적)."""
    msg = await db.get(models.AgentMessage, msg_id)
    if msg is None:
        return None
    msg.content = content
    await db.commit()
    await db.refresh(msg)

    # 실시간 스트리밍 업데이트 전송 (내용 업데이트)
    try:
        from app.services.stream_service import stream_manager
        await stream_manager.broadcast(msg.run_id, {
            "type": "content",
            "run_id": msg.run_id,
            "agent": msg.sender,
            "content": msg.content
        })
    except Exception:
        pass

    return msg


async def update_agent_message_status(
    db: AsyncSession, msg_id: str, status: str
) -> models.AgentMessage | None:
    """AgentMessage 상태 업데이트."""
    msg = await db.get(models.AgentMessage, msg_id)
    if msg is None:
        return None
    msg.status = status
    await db.commit()
    await db.refresh(msg)

    # 실시간 스트리밍 업데이트 전송 (상태 변경)
    try:
        from app.services.stream_service import stream_manager
        await stream_manager.broadcast(msg.run_id, {
            "type": "agent_status_changed",
            "run_id": msg.run_id,
            "agent_message_id": msg.id,
            "status": status
        })
    except Exception:
        pass

    return msg


async def get_all_memories(db: AsyncSession) -> list[models.GlobalMemory]:
    """전역 메모리 전체 목록 (생성순)."""
    result = await db.execute(
        select(models.GlobalMemory).order_by(models.GlobalMemory.created_at)
    )
    return list(result.scalars().all())


async def create_memory(db: AsyncSession, content: str) -> models.GlobalMemory:
    """전역 메모리 항목 생성. 빈 내용은 ValueError 발생."""
    content = content.strip()
    if not content:
        raise ValueError("메모리 내용이 비어 있습니다.")
    mem = models.GlobalMemory(content=content)
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


async def delete_memory(db: AsyncSession, memory_id: str) -> bool:
    """전역 메모리 항목 삭제. 없으면 False."""
    mem = await db.get(models.GlobalMemory, memory_id)
    if mem is None:
        return False
    await db.delete(mem)
    await db.commit()
    return True


async def get_agent_messages(
    db: AsyncSession, run_id: str
) -> list[models.AgentMessage]:
    """run_id에 해당하는 agent_messages 목록 (생성순)."""
    result = await db.execute(
        select(models.AgentMessage)
        .where(models.AgentMessage.run_id == run_id)
        .order_by(models.AgentMessage.created_at)
    )
    return list(result.scalars().all())
