#!/usr/bin/env bash
# =============================================================================
# Coworker macOS 빌드 스크립트 (DMG 생성)
#
# 사전 조건:
#   - Python 3.11+, pip, uv (백엔드 의존성)
#   - Node.js 18+, npm (프론트엔드 + Electron)
#   - PyInstaller: pip install pyinstaller
#
# 실행:
#   cd build_dmg
#   bash build.sh
# =============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build_dmg"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "========================================"
echo " Coworker macOS 빌드 시작"
echo " 프로젝트: $PROJECT_ROOT"
echo "========================================"

# ----------------------------------------------------------------------------
# STEP 1: React 프론트엔드 빌드
# ----------------------------------------------------------------------------
echo ""
echo "[1/4] React 프론트엔드 빌드..."
cd "$FRONTEND_DIR"
npm install
npm run build

# React 빌드 결과물 → backend/static/ 복사
echo "  → backend/static/ 에 복사"
rm -rf "$BACKEND_DIR/static"
cp -r "$FRONTEND_DIR/dist" "$BACKEND_DIR/static"

# ----------------------------------------------------------------------------
# STEP 2: PyInstaller로 백엔드 바이너리 생성
# ----------------------------------------------------------------------------
echo ""
echo "[2/4] PyInstaller 백엔드 번들 생성..."
cd "$BACKEND_DIR"

# 가상환경 활성화 (uv 사용 시)
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# 이전 빌드 정리
rm -rf dist/coworker-server build/coworker-server

pyinstaller "$BUILD_DIR/server.spec" --distpath "$BUILD_DIR/resources" --noconfirm

echo "  → $BUILD_DIR/resources/coworker-server 생성 완료"

# ----------------------------------------------------------------------------
# STEP 3: 앱 아이콘 확인
# ----------------------------------------------------------------------------
echo ""
echo "[3/4] 앱 아이콘 확인..."
if [ ! -f "$BUILD_DIR/assets/icon.icns" ]; then
  echo "  ⚠️  assets/icon.icns 가 없습니다."
  echo "     PNG → ICNS 변환: sips -s format icns icon.png --out icon.icns"
  echo "     임시로 기본 아이콘을 사용합니다."
fi

# ----------------------------------------------------------------------------
# STEP 4: Electron 패키징 (DMG 생성)
# ----------------------------------------------------------------------------
echo ""
echo "[4/4] Electron DMG 패키징..."
cd "$BUILD_DIR"
npm install
npm run build:mac

echo ""
echo "========================================"
echo " 빌드 완료!"
echo " 출력: $BUILD_DIR/dist/"
ls "$BUILD_DIR/dist/"*.dmg 2>/dev/null || true
echo "========================================"
