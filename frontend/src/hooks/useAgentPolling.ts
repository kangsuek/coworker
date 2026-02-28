// Agent Channel 메시지 폴링 훅 - 2초+지터, 조건부 (Sprint 6에서 구현)
export function useAgentPolling(
  _runId: string | null,
  _mode: 'solo' | 'team' | null,
  _isVisible: boolean,
) {
  return { messages: [], isPolling: false }
}
