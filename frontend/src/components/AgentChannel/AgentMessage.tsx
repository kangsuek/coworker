import type { AgentMessage } from '../../types/api'

const ROLE_COLORS: Record<string, string> = {
  Researcher: 'bg-blue-100 text-blue-700',
  Coder: 'bg-green-100 text-green-700',
  Reviewer: 'bg-yellow-100 text-yellow-700',
  Writer: 'bg-purple-100 text-purple-700',
  Planner: 'bg-orange-100 text-orange-700',
}

const STATUS_ICONS: Record<string, string> = {
  working: '⏳',
  done: '✅',
  error: '❌',
  cancelled: '⏹️',
}

interface Props {
  message: AgentMessage
}

function formatTime(isoString: string): string {
  const d = new Date(isoString)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}

export default function AgentMessageCard({ message }: Props) {
  const roleColor = ROLE_COLORS[message.role_preset] ?? 'bg-gray-100 text-gray-700'
  const statusIcon = STATUS_ICONS[message.status] ?? '⏳'
  const isWorking = message.status === 'working'

  return (
    <div className="bg-white rounded-lg border border-gray-200 mb-3 overflow-hidden">
      {/* 헤더: 역할 배지 + 이름 + 타임스탬프 + 상태 아이콘 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${roleColor}`}>
          {message.role_preset}
        </span>
        <span className="text-xs font-medium text-gray-700 flex-1 truncate">{message.sender}</span>
        <span className="text-xs text-gray-400">{formatTime(message.created_at)}</span>
        <span className="text-sm" title={message.status}>
          {statusIcon}
        </span>
      </div>

      {/* 본문: 중간 출력 (working 상태 → 커서 애니메이션) */}
      <div className="px-3 py-2.5">
        {message.content ? (
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
            {message.content}
            {isWorking && (
              <span className="inline-block w-1 h-3.5 bg-gray-500 ml-0.5 animate-pulse align-middle" />
            )}
          </pre>
        ) : (
          <p className="text-xs text-gray-400 italic">{isWorking ? '작업 중...' : '내용 없음'}</p>
        )}
      </div>
    </div>
  )
}
