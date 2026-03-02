from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Run, get_db
from app.models.schemas import SessionDetail, SessionOut, UserMessageOut
from app.services import session_service
from app.services.cli_service import cancel_current

_ACTIVE_RUN_STATUSES = {"queued", "thinking", "solo", "delegating", "working", "integrating"}

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """세션 목록 조회 (limit/offset 페이징)."""
    sessions = await session_service.list_sessions(db, limit=limit, offset=offset)
    return [
        SessionOut(id=s.id, title=s.title, created_at=s.created_at, updated_at=s.updated_at)
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_new_session(db: AsyncSession = Depends(get_db)):
    """새 세션 생성."""
    sess = await session_service.create_session(db)
    return SessionOut(
        id=sess.id, title=sess.title, created_at=sess.created_at, updated_at=sess.updated_at
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """세션 삭제 (관련 메시지·runs 포함).

    실행 중인 Run이 있으면 CLI 프로세스를 먼저 취소한 뒤 삭제한다.
    취소하지 않으면 백그라운드 태스크가 고아(orphan) 레코드를 생성한다.
    """
    result = await db.execute(
        select(Run).where(
            Run.session_id == session_id,
            Run.status.in_(_ACTIVE_RUN_STATUSES),
        )
    )
    if result.scalar_one_or_none() is not None:
        await cancel_current()

    deleted = await session_service.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """세션 상세 조회 (대화 히스토리 포함)."""
    session = await session_service.get_session_with_messages(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            UserMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                mode=m.mode,
                created_at=m.created_at,
            )
            for m in session.user_messages
        ],
    )
