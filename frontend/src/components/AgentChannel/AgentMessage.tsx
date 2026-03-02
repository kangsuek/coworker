import type { AgentMessage } from '../../types/api'

const ROLE_COLORS: Record<string, string> = {
  Researcher: 'bg-blue-900/30 text-blue-400 border border-blue-500/30',
  Coder: 'bg-green-900/30 text-green-400 border border-green-500/30',
  Reviewer: 'bg-yellow-900/30 text-yellow-400 border border-yellow-500/30',
  Writer: 'bg-purple-900/30 text-purple-400 border border-purple-500/30',
  Planner: 'bg-orange-900/30 text-orange-400 border border-orange-500/30',
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
  const roleColor = ROLE_COLORS[message.role_preset] ?? 'bg-white/10 text-gray-300 border border-white/20'
  const statusIcon = STATUS_ICONS[message.status] ?? '⏳'
  const isWorking = message.status === 'working'

  return (
    <div className="bg-[#141414] rounded-sm border border-white/10 mb-2 overflow-hidden font-mono">
      {/* 헤더: 역할 배지 + 이름 + 타임스탬프 + 상태 아이콘 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10 bg-[#0D0D0D]">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${roleColor}`}>
          {message.role_preset}
        </span>
        <span className="text-xs font-medium text-gray-300 flex-1 truncate">{message.sender}</span>
        <span className="text-xs text-gray-400">{formatTime(message.created_at)}</span>
        <span className="text-sm" title={message.status}>
          {statusIcon}
        </span>
      </div>

      {/* 본문: 중간 출력 (working 상태 → 커서 애니메이션) */}
      <div className="px-3 py-2.5">
        {message.content ? (
          <pre className="text-xs text-gray-400 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
            {message.content}
            {isWorking && (
              <span className="inline-block w-1 h-3.5 bg-[#0D0D0D]0 ml-0.5 animate-pulse align-middle" />
            )}
          </pre>
        ) : (
          <p className="text-xs text-gray-400 italic">{isWorking ? '작업 중...' : '내용 없음'}</p>
        )}
      </div>
    </div>
  )
}
