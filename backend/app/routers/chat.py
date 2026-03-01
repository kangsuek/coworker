from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reader import ReaderAgent
from app.models.db import Run, async_session, get_db
from app.models.schemas import (
    AgentMessageOut,
    AgentMessagesResponse,
    ChatRequest,
    ChatResponse,
    RunStatus,
)
from app.services.cli_service import cancel_current
from app.services.session_service import (
    create_run,
    create_session,
    create_user_message,
    get_agent_messages,
    get_session,
    update_run_status,
)

router = APIRouter(tags=["chat"])

_CANCELLABLE_STATUSES = {"queued", "thinking", "solo", "delegating", "working", "integrating"}


async def _run_reader_agent(session_id: str, user_message: str, run_id: str) -> None:
    """백그라운드 태스크: 자체 DB 세션으로 ReaderAgent 실행."""
    async with async_session() as db:
        await ReaderAgent(db).process_message(session_id, user_message, run_id)


@router.post("/chat", response_model=ChatResponse)
async def create_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """사용자 메시지 수신 → run 생성 → 백그라운드 처리 시작."""
    session = None
    if req.session_id:
        session = await get_session(db, req.session_id)
    if session is None:
        session = await create_session(db)

    user_msg = await create_user_message(db, session.id, "user", req.message)
    run = await create_run(db, session.id, user_msg.id)
    background_tasks.add_task(_run_reader_agent, session.id, req.message, run.id)
    return ChatResponse(run_id=run.id, session_id=session.id)


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """실행 상태 폴링 엔드포인트."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunStatus(status=run.status, response=run.response, mode=run.mode)


@router.get("/runs/{run_id}/agent-messages", response_model=AgentMessagesResponse)
async def get_agent_messages_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    """Agent Channel 중간 출력 폴링 엔드포인트."""
    messages = await get_agent_messages(db, run_id)
    return AgentMessagesResponse(
        messages=[
            AgentMessageOut(
                id=m.id,
                sender=m.sender,
                role_preset=m.role_preset,
                content=m.content,
                status=m.status,
                created_at=m.created_at,
            )
            for m in messages
        ],
        has_more=False,
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """실행 취소. 취소 가능한 상태가 아니면 무시."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in _CANCELLABLE_STATUSES:
        await cancel_current()
        await update_run_status(db, run_id, "cancelled")

    final_status = "cancelled" if run.status in _CANCELLABLE_STATUSES else run.status
    return {"run_id": run_id, "status": final_status}
