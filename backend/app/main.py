import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.db import engine, run_pragmas
from app.routers import chat, memory, sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await run_pragmas(conn)
    yield
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(memory.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# React 정적 파일 서빙 (패키징 빌드 전용)
# STATIC_DIR 환경변수가 설정된 경우에만 활성화된다.
# 개발 모드에서는 Vite dev server가 처리하므로 비활성.
# ---------------------------------------------------------------------------
_static_dir = Path(os.environ.get("STATIC_DIR", "")) or (
    Path(__file__).parent.parent / "static"
)

if _static_dir.exists():
    # /assets, /icons 등 정적 자원 직접 서빙
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    # SPA 라우팅: /api/** 를 제외한 모든 경로에서 index.html 반환
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(str(_static_dir / "index.html"))
