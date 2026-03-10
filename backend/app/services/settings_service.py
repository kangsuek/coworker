"""런타임 설정 서비스.

- DB `app_settings` 테이블을 단일 소스로 사용한다.
- 앱 시작 시 `load()` 를 호출하여 DB 값을 메모리 캐시에 로드한다.
- `get(key)` 는 캐시 → config 기본값 순으로 조회 (동기 호출 가능).
- `update()` 는 DB 저장 후 캐시를 즉시 갱신한다.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db import AppSetting

logger = logging.getLogger(__name__)

# UI에서 편집 가능한 설정과 각 기본값 (config.Settings → .env 기반)
SETTING_DEFAULTS: dict[str, str] = {
    # CLI 경로
    "claude_cli_path": settings.claude_cli_path,
    "gemini_cli_path": settings.gemini_cli_path,
    # 모델
    # 에이전트
    "max_sub_agents": str(settings.max_sub_agents),
    "team_trigger_header": settings.team_trigger_header,
    "role_add_trigger": settings.role_add_trigger,
    "memory_trigger": settings.memory_trigger,
    # 역할 키워드
    "role_researcher_keywords": settings.role_researcher_keywords,
    "role_writer_keywords": settings.role_writer_keywords,
    "role_planner_keywords": settings.role_planner_keywords,
    "role_coder_keywords": settings.role_coder_keywords,
    "role_reviewer_keywords": settings.role_reviewer_keywords,
    # 에이전트 프롬프트
    "prompt_agent_common": settings.prompt_agent_common,
    "prompt_researcher": settings.prompt_researcher,
    "prompt_researcher_web_search": settings.prompt_researcher_web_search,
    "prompt_coder": settings.prompt_coder,
    "prompt_reviewer": settings.prompt_reviewer,
    "prompt_writer": settings.prompt_writer,
    "prompt_planner": settings.prompt_planner,
}

# 메모리 캐시 (기본값으로 초기화)
_cache: dict[str, str] = dict(SETTING_DEFAULTS)


def get(key: str) -> str:
    """동기적으로 캐시된 설정값 반환. 키가 없으면 기본값, 그것도 없으면 빈 문자열."""
    return _cache.get(key, SETTING_DEFAULTS.get(key, ""))


def get_int(key: str) -> int:
    """정수형 설정값 반환."""
    try:
        return int(get(key))
    except (ValueError, TypeError):
        default = SETTING_DEFAULTS.get(key, "0")
        try:
            return int(default)
        except (ValueError, TypeError):
            return 0


def get_all() -> dict[str, str]:
    """현재 캐시된 모든 설정값 반환."""
    return {key: _cache.get(key, default) for key, default in SETTING_DEFAULTS.items()}


async def load(db: AsyncSession) -> None:
    """앱 시작 시 DB에서 모든 설정을 캐시에 로드한다."""
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    for row in rows:
        if row.key in SETTING_DEFAULTS:
            _cache[row.key] = row.value
    logger.info("런타임 설정 로드 완료: %d개 항목", len(rows))


async def update(db: AsyncSession, data: dict[str, Any]) -> dict[str, str]:
    """설정 일괄 업데이트. DB 저장 후 캐시 즉시 갱신.

    알 수 없는 키는 무시한다.
    빈 문자열은 기본값으로 리셋(DB에서 삭제)한다.
    """
    updated: dict[str, str] = {}

    for key, value in data.items():
        if key not in SETTING_DEFAULTS:
            continue
        value_str = str(value).strip()

        if value_str == "" or value_str == SETTING_DEFAULTS[key]:
            # 기본값과 같으면 DB에서 삭제 (기본값으로 리셋)
            await db.execute(delete(AppSetting).where(AppSetting.key == key))
            _cache[key] = SETTING_DEFAULTS[key]
        else:
            stmt = sqlite_insert(AppSetting).values(
                key=key, value=value_str
            ).on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value_str},
            )
            await db.execute(stmt)
            _cache[key] = value_str

        updated[key] = _cache[key]

    await db.commit()
    logger.info("설정 업데이트: %s", list(updated.keys()))
    return updated


async def reset_all(db: AsyncSession) -> None:
    """모든 설정을 기본값으로 리셋 (DB에서 전체 삭제)."""
    await db.execute(delete(AppSetting))
    await db.commit()
    _cache.update(SETTING_DEFAULTS)
    logger.info("모든 설정을 기본값으로 리셋")
