@echo off
REM =============================================================================
REM  Coworker Windows 빌드 스크립트 (EXE/NSIS 인스톨러 생성)
REM
REM  사전 조건:
REM    - Python 3.11+, pip
REM    - Node.js 18+, npm
REM    - PyInstaller: pip install pyinstaller
REM
REM  실행:
REM    cd build_dmg
REM    build-win.bat
REM =============================================================================

setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..
set BUILD_DIR=%~dp0
set BACKEND_DIR=%PROJECT_ROOT%\backend
set FRONTEND_DIR=%PROJECT_ROOT%\frontend

echo ========================================
echo  Coworker Windows 빌드 시작
echo  프로젝트: %PROJECT_ROOT%
echo ========================================

REM ----------------------------------------------------------------------------
REM STEP 1: React 프론트엔드 빌드
REM ----------------------------------------------------------------------------
echo.
echo [1/4] React 프론트엔드 빌드...
cd /d "%FRONTEND_DIR%"
call npm install
if %ERRORLEVEL% neq 0 ( echo [오류] npm install 실패 & exit /b 1 )
call npm run build
if %ERRORLEVEL% neq 0 ( echo [오류] npm run build 실패 & exit /b 1 )

REM React 빌드 결과물 → backend\static\ 복사
echo   -^> backend\static\ 에 복사
if exist "%BACKEND_DIR%\static" rmdir /s /q "%BACKEND_DIR%\static"
xcopy /e /i /q "%FRONTEND_DIR%\dist" "%BACKEND_DIR%\static"

REM ----------------------------------------------------------------------------
REM STEP 2: PyInstaller로 백엔드 바이너리 생성
REM ----------------------------------------------------------------------------
echo.
echo [2/4] PyInstaller 백엔드 번들 생성...
cd /d "%BACKEND_DIR%"

REM 가상환경 활성화 (존재 시)
if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

REM 이전 빌드 정리
if exist "%BUILD_DIR%resources\coworker-server" (
  rmdir /s /q "%BUILD_DIR%resources\coworker-server"
)

pyinstaller "%BUILD_DIR%server.spec" --distpath "%BUILD_DIR%resources" --noconfirm
if %ERRORLEVEL% neq 0 ( echo [오류] PyInstaller 실패 & exit /b 1 )

echo   -^> %BUILD_DIR%resources\coworker-server 생성 완료

REM ----------------------------------------------------------------------------
REM STEP 3: 앱 아이콘 확인
REM ----------------------------------------------------------------------------
echo.
echo [3/4] 앱 아이콘 확인...
if not exist "%BUILD_DIR%assets\icon.ico" (
  echo   [경고] assets\icon.ico 가 없습니다. 기본 아이콘을 사용합니다.
)

REM ----------------------------------------------------------------------------
REM STEP 4: Electron 패키징 (NSIS 인스톨러 생성)
REM ----------------------------------------------------------------------------
echo.
echo [4/4] Electron NSIS 패키징...
cd /d "%BUILD_DIR%"
call npm install
if %ERRORLEVEL% neq 0 ( echo [오류] npm install 실패 & exit /b 1 )
call npm run build:win
if %ERRORLEVEL% neq 0 ( echo [오류] electron-builder 실패 & exit /b 1 )

echo.
echo ========================================
echo  빌드 완료!
echo  출력: %BUILD_DIR%dist\
dir "%BUILD_DIR%dist\*.exe" 2>nul
echo ========================================

endlocal
