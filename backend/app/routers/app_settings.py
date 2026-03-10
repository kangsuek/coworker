"""앱 설정 API 라우터."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db
from app.services import settings_service

router = APIRouter(tags=["settings"])


class SettingsResponse(BaseModel):
    settings: dict[str, str]
    defaults: dict[str, str]


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, str]


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """현재 설정값 및 기본값 반환."""
    return SettingsResponse(
        settings=settings_service.get_all(),
        defaults=settings_service.SETTING_DEFAULTS,
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """설정 일괄 업데이트. 빈 문자열은 기본값으로 리셋."""
    await settings_service.update(db, req.settings)
    return SettingsResponse(
        settings=settings_service.get_all(),
        defaults=settings_service.SETTING_DEFAULTS,
    )


@router.delete("/settings")
async def reset_settings(db: AsyncSession = Depends(get_db)):
    """모든 설정을 기본값으로 리셋."""
    await settings_service.reset_all(db)
    return {"message": "모든 설정이 기본값으로 초기화되었습니다."}
