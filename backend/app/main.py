import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.db import async_session, engine, run_pragmas
from app.routers import chat, memory, sessions
from app.routers.app_settings import router as settings_router
from app.services import settings_service
from app.services.upload_service import UPLOAD_DIR, cleanup_expired_uploads

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


_CLEANUP_INTERVAL = 30 * 60  # 30분

logger = logging.getLogger(__name__)


async def _periodic_cleanup() -> None:
    """만료된 업로드 파일을 30분마다 정리한다."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        try:
            cleanup_expired_uploads(Path(UPLOAD_DIR), settings.upload_ttl_seconds)
        except Exception:
            logger.exception("업로드 파일 정기 정리 중 오류 발생")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await run_pragmas(conn)
        # app_settings 테이블 자동 생성 (없으면)
        from app.models.db import Base
        await conn.run_sync(Base.metadata.create_all)
    # DB에서 런타임 설정 로드
    async with async_session() as db:
        await settings_service.load(db)
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="Coworker API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(settings_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# React 정적 파일 서빙 (패키징 빌드 전용)
# STATIC_DIR 환경변수가 설정된 경우에만 활성화된다.
# 개발 모드에서는 Vite dev server가 처리하므로 비활성.
# ---------------------------------------------------------------------------
_static_env = os.environ.get("STATIC_DIR", "").strip()
_static_dir = Path(_static_env) if _static_env else (Path(__file__).parent.parent / "static")

if _static_dir.exists():
    # /assets, /icons 등 정적 자원 직접 서빙
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    # SPA 라우팅: /api/** 를 제외한 모든 경로에서 index.html 반환
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(str(_static_dir / "index.html"))
