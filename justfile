# Coworker - Task Runner (just)
# https://github.com/casey/just

# 개발 서버 실행 (백엔드 + 프론트엔드 동시)
dev:
    mkdir -p logs
    just backend & just frontend

# 백엔드 개발 서버
backend:
    mkdir -p logs
    cd backend && uv run uvicorn app.main:app --reload --port 8000 2>&1 | tee ../logs/backend.log

# 프론트엔드 개발 서버
frontend:
    mkdir -p logs
    cd frontend && npm run dev 2>&1 | tee ../logs/frontend.log

# 의존성 설치 + Claude CLI 확인
setup:
    @which claude || (echo "⚠ Warning: Claude CLI not found. Run: npm install -g @anthropic-ai/claude-code" && exit 1)
    cd backend && uv sync
    cd frontend && npm install

# DB 마이그레이션
migrate:
    cd backend && uv run alembic upgrade head

# 테스트
test:
    cd backend && uv run pytest -v

# 코드 포맷·린트
lint:
    cd backend && uv run ruff check . && uv run ruff format .
    cd frontend && npm run lint

# macOS 앱 개발 모드 (Phase 2)
app-dev:
    cd tauri && npm run tauri dev

# macOS 앱 빌드 (Phase 2)
app-build:
    cd tauri && npm run tauri build
