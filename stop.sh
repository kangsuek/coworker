#!/bin/bash

echo "🛑 Coworker 서버를 종료합니다..."

# 포트 8000(백엔드)을 사용 중인 프로세스 찾아서 종료
BACKEND_PID=$(lsof -t -i:8000)
if [ -n "$BACKEND_PID" ]; then
  echo "백엔드 프로세스 종료 (PID: $BACKEND_PID)"
  kill -9 $BACKEND_PID
fi

# 포트 5173(프론트엔드)을 사용 중인 프로세스 찾아서 종료
FRONTEND_PID=$(lsof -t -i:5173)
if [ -n "$FRONTEND_PID" ]; then
  echo "프론트엔드 프로세스 종료 (PID: $FRONTEND_PID)"
  kill -9 $FRONTEND_PID
fi

# 백그라운드에 남아있을 수 있는 just 프로세스 종료
pkill -f "just dev"
pkill -f "just backend"
pkill -f "just frontend"

echo "✅ 모든 서버가 정상적으로 종료되었습니다."
