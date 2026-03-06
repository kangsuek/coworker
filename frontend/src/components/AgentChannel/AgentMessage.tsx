import { Check, Loader2, X, CircleDot } from 'lucide-react'
import type { AgentMessage } from '../../types/api'

const ROLE_COLORS: Record<string, string> = {
  Researcher: 'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800/50',
  Coder: 'bg-green-50 text-green-600 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800/50',
  Reviewer: 'bg-yellow-50 text-yellow-600 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800/50',
  Writer: 'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-900/20 dark:text-purple-400 dark:border-purple-800/50',
  Planner: 'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800/50',
}

interface Props {
  message: AgentMessage
}

function formatTime(isoString: string): string {
  const d = new Date(isoString)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}

export default function AgentMessageCard({ message }: Props) {
  const roleColor = ROLE_COLORS[message.role_preset] ?? 'bg-zinc-100 text-zinc-600 border-zinc-200 dark:bg-zinc-800/50 dark:text-zinc-400 dark:border-zinc-700'
  const isWorking = message.status === 'working'

  return (
    <div className="rounded-xl border p-4 transition-all shadow-sm bg-white border-zinc-200 dark:bg-zinc-900/40 dark:border-zinc-800/80 mb-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className={`px-2.5 py-1 rounded-md text-xs font-bold tracking-wide border ${roleColor}`}>
            {message.role_preset}
          </span>
          <span className="text-sm font-semibold font-mono text-zinc-700 dark:text-zinc-300 flex-1 truncate">
            {message.sender}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
          {formatTime(message.created_at)}
          
          {message.status === 'done' && (
            <div className="bg-emerald-500 rounded text-zinc-50 dark:text-zinc-950 p-0.5" title="완료">
              <Check size={12} strokeWidth={3} />
            </div>
          )}
          {message.status === 'error' && (
            <div className="bg-red-500 rounded text-zinc-50 dark:text-zinc-950 p-0.5" title="오류">
              <X size={12} strokeWidth={3} />
            </div>
          )}
          {message.status === 'working' && (
            <div className="text-emerald-500" title="작업 중">
              <Loader2 size={16} strokeWidth={2.5} className="animate-spin" />
            </div>
          )}
          {message.status === 'cancelled' && (
            <div className="text-zinc-400" title="취소됨">
              <CircleDot size={14} strokeWidth={2.5} />
            </div>
          )}
        </div>
      </div>

      <div className="text-[13px] leading-relaxed space-y-2 text-zinc-600 dark:text-zinc-300">
        {message.content ? (
          <div className="whitespace-pre-wrap break-words max-h-64 overflow-y-auto font-sans scrollbar-hide">
            {message.content}
            {isWorking && (
              <span className="inline-block w-1 h-3.5 bg-zinc-400 dark:bg-zinc-500 ml-0.5 animate-pulse align-middle" />
            )}
          </div>
        ) : (
          <p className="italic text-zinc-400 dark:text-zinc-500">{isWorking ? '작업 중...' : '내용 없음'}</p>
        )}
      </div>
    </div>
  )
}