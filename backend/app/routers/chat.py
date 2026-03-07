import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reader import ReaderAgent
from app.config import settings
from app.models.db import Run, async_session, get_db
from app.models.schemas import (
    AgentMessageOut,
    AgentMessagesResponse,
    ChatRequest,
    ChatResponse,
    RunStatus,
    TimingInfo,
)
from app.services.cli_service import cancel_current
from app.services.llm import get_allowed_provider_names
from app.services.session_service import (
    create_run,
    create_session,
    create_user_message,
    get_agent_messages,
    get_session,
    update_run_status,
)
from app.services.stream_service import stream_manager

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
    allowed = get_allowed_provider_names()
    if req.llm_provider is not None and req.llm_provider not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid llm_provider. Allowed: {allowed}",
        )
    session = None
    if req.session_id:
        session = await get_session(db, req.session_id)
        if session:
            # 세션 설정 업데이트 (UI에서 모델 변경 시)
            updated = False
            if req.llm_provider and session.llm_provider != req.llm_provider:
                session.llm_provider = req.llm_provider
                updated = True
            if req.llm_model is not None and session.llm_model != req.llm_model:
                session.llm_model = req.llm_model
                updated = True
            if updated:
                db.add(session)
                await db.commit()

    if session is None:
        session = await create_session(
            db,
            llm_provider=req.llm_provider or "claude-cli",
            llm_model=req.llm_model
        )

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
    session = await get_session(db, run.session_id)
    if session and session.llm_model:
        model = session.llm_model
    else:
        model = (
            settings.solo_model or None if run.mode == "solo"
            else settings.team_model or None if run.mode == "team"
            else None
        )
    timing = None
    if any([run.started_at, run.thinking_started_at, run.cli_started_at]):
        timing = TimingInfo(
            queued_at=run.started_at,
            thinking_started_at=run.thinking_started_at,
            cli_started_at=run.cli_started_at,
            finished_at=run.finished_at,
        )
    return RunStatus(
        status=run.status, response=run.response, mode=run.mode, model=model, timing=timing
    )


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
        await cancel_current(run_id=run_id)
        await update_run_status(db, run_id, "cancelled")

    final_status = "cancelled" if run.status in _CANCELLABLE_STATUSES else run.status
    return {"run_id": run_id, "status": final_status}


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str):
    """실시간 상태 및 에이전트 출력 스트리밍 엔드포인트."""

    async def event_generator():
        # 구독 시작
        queue = await stream_manager.subscribe(run_id)
        # 연결 직후 한 번 전송해 클라이언트가 응답/스트림을 즉시 수신하도록 함 (테스트·프록시 호환)
        yield "data: {\"type\":\"connected\",\"run_id\":\"" + run_id + "\"}\n\n"
        try:
            while True:
                # 큐에서 새로운 메시지 대기
                data = await queue.get()
                # SSE 포맷으로 데이터 전송
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            # 클라이언트 연결 종료 시 구독 해제
            await stream_manager.unsubscribe(run_id, queue)
        except Exception:
            await stream_manager.unsubscribe(run_id, queue)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 방지
        },
    )
