import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reader import ReaderAgent
from app.config import settings
from app.models.db import Run, async_session, get_db
from app.models.schemas import (
    CANCELLABLE_STATUSES,
    AgentMessageOut,
    AgentMessagesResponse,
    ChatRequest,
    ChatResponse,
    RunStatus,
    TimingInfo,
)
from app.services.cli_service import cancel_current, get_active_cli_count
from app.services.llm import get_allowed_provider_names
from app.services.upload_service import UPLOAD_DIR, cleanup_expired_uploads, get_upload_path, save_upload

MAX_UPLOAD_SIZE_BYTES: int = settings.upload_max_size_mb * 1024 * 1024
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


async def _run_reader_agent(
    session_id: str, user_message: str, run_id: str,
    file_paths: list[str] | None = None,
) -> None:
    """백그라운드 태스크: 자체 DB 세션으로 ReaderAgent 실행."""
    async with async_session() as db:
        await ReaderAgent(db).process_message(session_id, user_message, run_id, file_paths=file_paths or [])


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
            llm_provider=req.llm_provider or "gemini-cli",
            llm_model=req.llm_model
        )

    user_msg = await create_user_message(db, session.id, "user", req.message)
    run = await create_run(db, session.id, user_msg.id)
    # file_ids → 실제 파일 경로 변환 (존재하지 않는 ID는 건너뜀)
    file_paths: list[str] = []
    for fid in (req.file_ids or []):
        path = get_upload_path(fid, Path(UPLOAD_DIR))
        if path:
            file_paths.append(str(path))

    background_tasks.add_task(_run_reader_agent, session.id, req.message, run.id, file_paths)
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

    if run.status in CANCELLABLE_STATUSES:
        await cancel_current(run_id=run_id)
        await update_run_status(db, run_id, "cancelled")

    final_status = "cancelled" if run.status in CANCELLABLE_STATUSES else run.status
    return {"run_id": run_id, "status": final_status}


@router.get("/cli/status")
async def get_cli_status():
    """현재 실행 중인 CLI 프로세스 수 반환."""
    return {"active_cli_count": get_active_cli_count()}


@router.post("/upload", status_code=200)
async def upload_files(files: list[UploadFile]):
    """첨부 파일을 임시 저장 후 file_id 목록 반환.

    - 파일이 없으면 422
    - 허용되지 않는 확장자가 하나라도 있으면 422 (전체 거부)
    - 파일 크기 초과 시 413
    """
    if not files:
        raise HTTPException(status_code=422, detail="첨부 파일이 없습니다.")

    upload_dir = Path(UPLOAD_DIR)
    uploaded = []
    for file in files:
        try:
            result = await save_upload(file, upload_dir, MAX_UPLOAD_SIZE_BYTES)
        except ValueError as e:
            msg = str(e)
            if "파일 크기" in msg:
                raise HTTPException(status_code=413, detail=msg)
            raise HTTPException(status_code=422, detail=msg)
        uploaded.append({
            "file_id": result["file_id"],
            "filename": result["filename"],
            "size": result["size"],
        })

    return {"uploaded": uploaded}


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
