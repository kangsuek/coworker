"""전역 메모리 CRUD API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db
from app.models.schemas import MemoryCreateRequest, MemoryOut
from app.services import session_service

router = APIRouter(tags=["memory"])


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(db: AsyncSession = Depends(get_db)):
    """전역 메모리 전체 조회."""
    memories = await session_service.get_all_memories(db)
    return [MemoryOut(id=m.id, content=m.content, created_at=m.created_at) for m in memories]


@router.post("/memories", response_model=MemoryOut, status_code=201)
async def create_memory(body: MemoryCreateRequest, db: AsyncSession = Depends(get_db)):
    """전역 메모리 항목 추가."""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="content must not be empty")
    mem = await session_service.create_memory(db, body.content)
    return MemoryOut(id=mem.id, content=mem.content, created_at=mem.created_at)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, db: AsyncSession = Depends(get_db)):
    """전역 메모리 항목 삭제."""
    deleted = await session_service.delete_memory(db, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
