# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Coworker Backend Server.

빌드 방법:
    cd /path/to/coworker/backend
    pyinstaller ../build_dmg/server.spec
"""

import sys
from pathlib import Path

# 경로 기준: backend/ 디렉토리 (pyinstaller 실행 위치)
BACKEND_DIR = Path(SPECPATH).parent / 'backend'
BUILD_DIR   = Path(SPECPATH)          # build_dmg/

a = Analysis(
    [str(BUILD_DIR / 'run_server.py')],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=[
        # React 빌드 결과물 (build.sh에서 복사 완료 후 실행)
        (str(BACKEND_DIR / 'static'), 'static'),
    ],
    hiddenimports=[
        # uvicorn
        'uvicorn',
        'uvicorn.main',
        'uvicorn.config',
        'uvicorn.lifespan.on',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.logging',
        # FastAPI / Starlette
        'fastapi',
        'starlette.middleware.cors',
        'starlette.staticfiles',
        'starlette.responses',
        # SQLAlchemy / aiosqlite
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.ext.asyncio',
        'aiosqlite',
        # pydantic
        'pydantic_settings',
        # 앱 모듈
        'app.main',
        'app.config',
        'app.models.db',
        'app.models.schemas',
        'app.routers.chat',
        'app.routers.sessions',
        'app.routers.memory',
        'app.agents.reader',
        'app.agents.sub_agent',
        'app.agents.presets.coder',
        'app.agents.presets.planner',
        'app.agents.presets.researcher',
        'app.agents.presets.reviewer',
        'app.agents.presets.writer',
        'app.services.classification',
        'app.services.cli_service',
        'app.services.session_service',
        'app.services.stream_service',
        'app.services.llm',
        'app.services.llm.base',
        'app.services.llm.claude_cli',
        'app.services.llm.gemini_cli',
        # 기타
        'h11',
        'anyio',
        'anyio._backends._asyncio',
        'sniffio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='coworker-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # 콘솔 창 표시 (로그 확인용)
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='coworker-server',
)
