// 실행 상태 폴링 훅 - 2초+지터 간격 (Sprint 4에서 구현)
export function useRunPolling(_runId: string | null) {
  return { status: null, progress: null, response: null, mode: null, agents: null }
}
