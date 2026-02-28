from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db
from app.models.schemas import SessionDetail, SessionOut

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """세션 목록 조회."""
    # TODO: Sprint 3에서 구현
    raise NotImplementedError


@router.post("/sessions", response_model=SessionOut)
async def create_session(db: AsyncSession = Depends(get_db)):
    """새 세션 생성."""
    # TODO: Sprint 3에서 구현
    raise NotImplementedError


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """세션 상세 조회 (대화 히스토리 포함)."""
    # TODO: Sprint 3에서 구현
    raise NotImplementedError
