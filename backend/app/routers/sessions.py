from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Run, get_db
from app.models.schemas import SessionDetail, SessionOut, TimingInfo, UserMessageOut
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
        SessionOut(
            id=s.id,
            title=s.title,
            llm_provider=s.llm_provider,
            llm_model=s.llm_model,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_new_session(db: AsyncSession = Depends(get_db)):
    """새 세션 생성."""
    sess = await session_service.create_session(db)
    return SessionOut(
        id=sess.id,
        title=sess.title,
        llm_provider=sess.llm_provider,
        llm_model=sess.llm_model,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
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

    # user_message_id → run 정보 매핑 (run_id, timing 포함)
    runs_result = await db.execute(
        select(
            Run.id,
            Run.user_message_id,
            Run.started_at,
            Run.thinking_started_at,
            Run.cli_started_at,
            Run.finished_at,
        ).where(Run.session_id == session_id)
    )
    run_map: dict[str, dict] = {
        row.user_message_id: {
            "id": row.id,
            "timing": TimingInfo(
                queued_at=row.started_at,
                thinking_started_at=row.thinking_started_at,
                cli_started_at=row.cli_started_at,
                finished_at=row.finished_at,
            ) if row.finished_at else None,
        }
        for row in runs_result
    }

    # 메시지를 시간순 정렬
    sorted_msgs = sorted(session.user_messages, key=lambda m: m.created_at)
    session_model = session.llm_model  # 세션에 설정된 모델명

    last_team_run_id: str | None = None
    result_messages: list[UserMessageOut] = []
    for i, m in enumerate(sorted_msgs):
        run_id: str | None = None
        timing: TimingInfo | None = None
        if m.role == "reader" and m.mode == "team":
            # 직전 user 메시지의 run_id를 연결
            for j in range(i - 1, -1, -1):
                if sorted_msgs[j].role == "user":
                    run_info = run_map.get(sorted_msgs[j].id)
                    if run_info:
                        run_id = run_info["id"]
                        timing = run_info["timing"]
                    break
            if run_id:
                last_team_run_id = run_id
        result_messages.append(
            UserMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                mode=m.mode,
                run_id=run_id,
                model=session_model if run_id else None,
                timing=timing,
                created_at=m.created_at,
            )
        )

    return SessionDetail(
        id=session.id,
        title=session.title,
        llm_provider=session.llm_provider,
        llm_model=session.llm_model,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=result_messages,
        last_team_run_id=last_team_run_id,
    )
