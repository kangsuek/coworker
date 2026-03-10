#!/usr/bin/env bash
# =============================================================================
# Coworker 빌드 스크립트 (루트)
#
# 사용법:
#   ./build_dmg.sh          # 현재 OS에 맞게 자동 빌드
#   ./build_dmg.sh --mac    # macOS DMG만 빌드
#   ./build_dmg.sh --win    # Windows EXE만 빌드 (Windows PC에서 실행)
#   ./build_dmg.sh --all    # DMG + EXE 모두 빌드 (macOS 기준, cross-build)
#
# 사전 조건:
#   - Python 3.11+, pip
#   - Node.js 18+, npm
#   - PyInstaller: pip install pyinstaller
#
# 출력:
#   build_dmg/dist/Coworker-1.0.0.dmg      (macOS)
#   build_dmg/dist/Coworker Setup 1.0.0.exe (Windows)
# =============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_ROOT/build_dmg"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 인수 파싱
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    TARGET="--mac"
  else
    TARGET="--win"
  fi
fi

echo "========================================"
echo " Coworker 빌드 시작"
echo " 프로젝트: $PROJECT_ROOT"
echo " 타겟: $TARGET"
echo "========================================"

# ----------------------------------------------------------------------------
# STEP 1: React 프론트엔드 빌드 (공통)
# ----------------------------------------------------------------------------
echo ""
echo "[1/4] React 프론트엔드 빌드..."
cd "$FRONTEND_DIR"
npm install
npm run build

echo "  → backend/static/ 에 복사"
rm -rf "$BACKEND_DIR/static"
cp -r "$FRONTEND_DIR/dist" "$BACKEND_DIR/static"

# ----------------------------------------------------------------------------
# STEP 2: PyInstaller 백엔드 바이너리 생성
# ----------------------------------------------------------------------------
echo ""
echo "[2/4] PyInstaller 백엔드 번들 생성..."
cd "$BACKEND_DIR"

# 이전 빌드 정리
rm -rf "$BUILD_DIR/resources/coworker-server"

# pyinstaller 실행: uv run → venv → 시스템 순서로 탐색
if command -v uv &>/dev/null && [ -f "pyproject.toml" ]; then
  uv run pyinstaller "$BUILD_DIR/server.spec" --distpath "$BUILD_DIR/resources" --noconfirm
elif [ -f ".venv/bin/pyinstaller" ]; then
  .venv/bin/pyinstaller "$BUILD_DIR/server.spec" --distpath "$BUILD_DIR/resources" --noconfirm
elif command -v pyinstaller &>/dev/null; then
  pyinstaller "$BUILD_DIR/server.spec" --distpath "$BUILD_DIR/resources" --noconfirm
else
  echo "  [오류] pyinstaller를 찾을 수 없습니다."
  echo "         설치: cd backend && uv add pyinstaller --dev"
  exit 1
fi
echo "  → $BUILD_DIR/resources/coworker-server 생성 완료"

# ----------------------------------------------------------------------------
# STEP 3: 아이콘 확인
# ----------------------------------------------------------------------------
echo ""
echo "[3/4] 아이콘 확인..."
if [ "$TARGET" = "--mac" ] || [ "$TARGET" = "--all" ]; then
  if [ ! -f "$BUILD_DIR/assets/icon.icns" ]; then
    echo "  ⚠️  assets/icon.icns 없음 — 기본 아이콘 사용"
  else
    echo "  ✓ icon.icns"
  fi
fi
if [ "$TARGET" = "--win" ] || [ "$TARGET" = "--all" ]; then
  if [ ! -f "$BUILD_DIR/assets/icon.ico" ]; then
    echo "  ⚠️  assets/icon.ico 없음 — 기본 아이콘 사용"
  else
    echo "  ✓ icon.ico"
  fi
fi

# ----------------------------------------------------------------------------
# STEP 4: Electron 패키징
# ----------------------------------------------------------------------------
echo ""
echo "[4/4] Electron 패키징..."
cd "$BUILD_DIR"

# 이전 빌드 DMG 마운트 잔여물 정리
echo "  → 기존 Coworker 볼륨 마운트 해제..."
while IFS= read -r vol; do
  [ -z "$vol" ] && continue
  echo "     해제 중: $vol"
  hdiutil detach "$vol" -force 2>/dev/null || true
done < <(hdiutil info 2>/dev/null | grep '/Volumes/Coworker' | awk '{print $NF}')
# glob 방식 추가 보완
for vol in "/Volumes/Coworker" /Volumes/Coworker\ *; do
  if [ -d "$vol" ]; then
    echo "     해제 중: $vol"
    hdiutil detach "$vol" -force 2>/dev/null || true
  fi
done
sleep 1

npm install

# 이전 빌드 결과물 정리 (충돌 방지)
echo "  → 이전 dist/ 정리..."
rm -rf "$BUILD_DIR/dist"

if [ "$TARGET" = "--mac" ]; then
  echo "  → macOS DMG 빌드 중..."
  npm run build:mac
elif [ "$TARGET" = "--win" ]; then
  echo "  → Windows EXE 빌드 중..."
  echo "  ⚠️  Windows EXE 빌드는 Windows PC에서 실행을 권장합니다."
  echo "     macOS에서 cross-build 시 백엔드 바이너리가 macOS 바이너리이므로"
  echo "     Electron 인스톨러만 생성됩니다 (백엔드 미포함)."
  npm run build:win
elif [ "$TARGET" = "--all" ]; then
  echo "  → macOS DMG 빌드 중..."
  npm run build:mac
  echo "  → Windows EXE 빌드 중..."
  echo "  ⚠️  Windows EXE cross-build: 인스톨러만 생성됩니다."
  npm run build:win
else
  echo "  [오류] 알 수 없는 타겟: $TARGET"
  echo "  사용법: ./build_dmg.sh [--mac|--win|--all]"
  exit 1
fi

# ----------------------------------------------------------------------------
# 결과 출력
# ----------------------------------------------------------------------------
echo ""
echo "========================================"
echo " 빌드 완료!"
echo " 출력: $BUILD_DIR/dist/"
echo ""
ls "$BUILD_DIR/dist/"*.dmg 2>/dev/null && true
ls "$BUILD_DIR/dist/"*.exe 2>/dev/null && true
echo "========================================"
