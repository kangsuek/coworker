"""Coworker 백엔드 서버 엔트리 포인트 (PyInstaller 패키징용).

개발 시:  python run_server.py --port 8000
패키징 후: coworker-server --port 18765
"""

import argparse
import asyncio
import os
import platform
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """OS별 사용자 앱 데이터 디렉토리 반환."""
    system = platform.system()
    if system == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / 'coworker'
    elif system == 'Windows':
        appdata = os.environ.get('APPDATA', str(Path.home()))
        return Path(appdata) / 'coworker'
    return Path.home() / '.coworker'


def get_bundle_dir() -> Path:
    """PyInstaller 번들 또는 소스 루트 디렉토리 반환."""
    if getattr(sys, 'frozen', False):
        # PyInstaller 6.x --onedir 모드: datas는 _internal/ (_MEIPASS)에 추출됨
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    # 개발 모드: build_dmg/ → 프로젝트 루트 → backend/
    return Path(__file__).parent.parent / 'backend'


def setup_paths(bundle_dir: Path, data_dir: Path, port: int) -> None:
    """환경변수 및 Python 경로 설정."""
    # 백엔드 소스 경로를 sys.path에 추가 (PyInstaller 미사용 시)
    if not getattr(sys, 'frozen', False):
        sys.path.insert(0, str(bundle_dir))

    # DB 경로: 사용자 데이터 디렉토리에 저장
    os.environ['DB_PATH'] = str(data_dir / 'coworker.db')

    # CORS: Electron 내부 요청 허용
    os.environ['CORS_ORIGINS'] = f'http://localhost:{port},http://127.0.0.1:{port}'

    # 정적 파일 디렉토리 (React 빌드 결과물)
    static_dir = bundle_dir / 'static'
    os.environ['STATIC_DIR'] = str(static_dir)


async def init_db() -> None:
    """DB 스키마 초기화 (create_all — 신규 설치 시)."""
    from app.models.db import Base, engine, run_pragmas
    async with engine.begin() as conn:
        await run_pragmas(conn)
        await conn.run_sync(Base.metadata.create_all)


def main() -> None:
    parser = argparse.ArgumentParser(description='Coworker Backend Server')
    parser.add_argument('--port', type=int, default=18765, help='서버 포트')
    parser.add_argument('--host', default='127.0.0.1', help='바인딩 주소')
    args = parser.parse_args()

    bundle_dir = get_bundle_dir()
    data_dir = get_app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    setup_paths(bundle_dir, data_dir, args.port)

    # DB 초기화
    asyncio.run(init_db())

    # uvicorn으로 FastAPI 앱 실행
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level='info',
        access_log=False,
    )


if __name__ == '__main__':
    main()
