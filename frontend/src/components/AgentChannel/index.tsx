interface Props {
  mode: 'solo' | 'team' | null
}

export default function AgentChannel({ mode }: Props) {
  return (
    <div className="w-[420px] flex flex-col bg-gray-50/80 shrink-0">
      <header className="px-4 py-3 border-b border-gray-200 bg-white shrink-0">
        <span className="font-medium text-gray-800">Agent Channel</span>
      </header>

      <div className="flex-1 flex items-center justify-center">
        {mode === 'team' ? (
          // Sprint 6에서 구현
          <div className="text-center text-gray-400">
            <p className="text-2xl mb-2">⚙️</p>
            <p className="text-sm">Team 작업 중...</p>
          </div>
        ) : (
          <div className="text-center text-gray-400">
            <p className="text-3xl mb-3">🤖</p>
            <p className="text-sm font-medium">대기 중</p>
            <p className="text-xs mt-1.5 text-gray-300">Team 작업이 시작되면</p>
            <p className="text-xs text-gray-300">Agent 간 대화가 표시됩니다</p>
          </div>
        )}
      </div>
    </div>
  )
}
