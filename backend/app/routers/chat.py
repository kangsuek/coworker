from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db
from app.models.schemas import (
    AgentMessagesResponse,
    ChatRequest,
    ChatResponse,
    RunStatus,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def create_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """사용자 메시지 수신 → run 생성 → 백그라운드 처리 시작."""
    # TODO: Sprint 3에서 구현
    raise NotImplementedError


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """실행 상태 폴링 엔드포인트."""
    # TODO: Sprint 3에서 구현
    raise NotImplementedError


@router.get("/runs/{run_id}/agent-messages", response_model=AgentMessagesResponse)
async def get_agent_messages(run_id: str, db: AsyncSession = Depends(get_db)):
    """Agent Channel 중간 출력 폴링 엔드포인트."""
    # TODO: Sprint 5에서 구현
    raise NotImplementedError


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """실행 취소."""
    # TODO: Sprint 5에서 구현
    raise NotImplementedError
