#!/bin/bash

echo "🚀 Coworker 서버를 백그라운드에서 시작합니다..."
echo "==================================================="

# logs 폴더 생성
mkdir -p logs

# 기존 포트 점유 확인 및 종료
./stop.sh

# 백그라운드에서 just dev 실행
nohup just dev > /dev/null 2>&1 &

echo "✅ 서버가 백그라운드에서 실행되었습니다."
echo "   - Frontend (UI): http://localhost:5173"
echo "   - Backend (API): http://localhost:8000"
echo ""
echo "📝 로그를 확인하려면 다음 명령어를 사용하세요:"
echo "   - 백엔드: tail -f logs/backend.log"
echo "   - 프론트엔드: tail -f logs/frontend.log"
echo "==================================================="
