# 코드 리뷰 (Code Review) - Sprint 5 & 6 진행 현황

## 3. 남은 태스크 및 개선 제안 (Sprint 6 마무리)
현재 `docs/TODO.md`를 보면 **Sprint 6의 '전체 통합 테스트(수동 E2E 테스트 및 분류 정확도 테스트)'** 항목만 비어 있는 상태입니다. (8/9 진행 중)

1. **분류 정확도 검증**: ~~프롬프트의 분류가 실제로 20개 케이스 중 18개 이상 정확하게 `solo` / `team`으로 라우팅되는지 확인하는 추가적인 테스트 케이스 작성을 권장합니다.~~
   - ✅ **적용 완료**: `backend/tests/test_classification.py`에 solo 10개 + team 10개 = 20개 파라미터화 테스트 추가. 90% 이상 정확도 일괄 검증 테스트(`test_routing_accuracy_at_least_90_percent`) 포함. 추가 엣지 케이스 5개(마크다운 코드블록, 후행 텍스트, 5개 역할 전부 사용, 빈 문자열, 중첩 JSON) 포함. 전체 30개 테스트 통과.
2. **에러 바운더리(Error Boundary)**: ~~Agent Channel 렌더링 도중 예기치 못한 프론트엔드 크래시가 발생할 수 있으므로, React의 ErrorBoundary 적용을 고려해 보세요.~~
   - ✅ **적용 완료**: `frontend/src/components/ErrorBoundary.tsx` 생성. `App.tsx`에서 `<AgentChannel>`을 `<ErrorBoundary fallbackLabel="Agent Channel">`로 래핑. 오류 발생 시 에러 메시지 + "다시 시도" 버튼 표시.
3. **Agent Channel 내보내기 다운로드 UX**: ~~내보내기 생성 직후 사용자에게 시각적인 피드백(다운로드 완료 토스트 메시지 등)을 주면 사용성이 더욱 향상될 것입니다.~~
   - ✅ **적용 완료**: `AgentChannel/index.tsx`에 토스트 알림 구현. TXT/JSON 내보내기 시 "✓ TXT 파일이 다운로드되었습니다" / "✓ JSON 파일이 다운로드되었습니다" 메시지가 2.5초간 표시 후 자동 소멸.