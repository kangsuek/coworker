# Coworker Desktop 빌드 가이드

## 사전 조건

| 도구 | 버전 | 설치 |
|------|------|------|
| Python | 3.11+ | python.org |
| Node.js | 18+ | nodejs.org |
| PyInstaller | 최신 | `pip install pyinstaller` |
| Claude CLI | 최신 | anthropic.com |
| Gemini CLI | 최신 | gemini.google.com |

---

## 아이콘 준비 (필수)

`assets/` 폴더에 아이콘 파일을 준비합니다.

### macOS (.icns)
```bash
# 1024x1024 PNG → .icns 변환
mkdir icon.iconset
sips -z 16   16   icon.png --out icon.iconset/icon_16x16.png
sips -z 32   32   icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32   32   icon.png --out icon.iconset/icon_32x32.png
sips -z 64   64   icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128  128  icon.png --out icon.iconset/icon_128x128.png
sips -z 256  256  icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256  256  icon.png --out icon.iconset/icon_256x256.png
sips -z 512  512  icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512  512  icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset -o assets/icon.icns
```

### Windows (.ico)
```bash
# ImageMagick 사용
magick icon.png -resize 256x256 assets/icon.ico
```

---

## macOS DMG 빌드

```bash
cd build_dmg
bash build.sh
# 결과: build_dmg/dist/Coworker-1.0.0.dmg
```

## Windows EXE 빌드 (Windows PC에서 실행)

```bat
cd build_dmg
build-win.bat
REM 결과: build_dmg\dist\Coworker Setup 1.0.0.exe
```

---

## 빌드 순서 (내부)

```
1. npm run build (frontend)          → frontend/dist/
2. cp frontend/dist → backend/static/
3. pyinstaller server.spec           → build_dmg/resources/coworker-server/
4. electron-builder                  → build_dmg/dist/*.dmg (또는 *.exe)
```

---

## 디렉토리 구조

```
build_dmg/
├── main.js            Electron 메인 프로세스
├── package.json       Electron + electron-builder 설정
├── run_server.py      PyInstaller 엔트리 포인트
├── server.spec        PyInstaller 스펙
├── build.sh           macOS 빌드 스크립트
├── build-win.bat      Windows 빌드 스크립트
├── assets/
│   ├── icon.icns      macOS 아이콘 (직접 준비)
│   └── icon.ico       Windows 아이콘 (직접 준비)
├── resources/         빌드 후 자동 생성
│   └── coworker-server/  PyInstaller 바이너리
└── dist/              최종 패키지 출력
    ├── Coworker-1.0.0.dmg
    └── Coworker Setup 1.0.0.exe
```

---

## 사용자 데이터 경로

앱이 설치된 후 데이터는 아래 경로에 저장됩니다.

| OS | 경로 |
|----|------|
| macOS | `~/Library/Application Support/coworker/coworker.db` |
| Windows | `%APPDATA%\coworker\coworker.db` |
