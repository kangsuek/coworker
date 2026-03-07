import { Check, Loader2, X, CircleDot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

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

      <div className="text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-300">
        {message.content ? (
          <div
            className="max-h-96 overflow-y-auto scrollbar-hide max-w-none
              [&_p]:mb-2 [&_p:last-child]:mb-0
              [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2
              [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2
              [&_li]:mb-1
              [&_h1]:text-sm [&_h1]:font-bold [&_h1]:mb-2
              [&_h2]:text-[13px] [&_h2]:font-bold [&_h2]:mb-2
              [&_h3]:text-[13px] [&_h3]:font-semibold [&_h3]:mb-1
              [&_pre]:my-2 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:bg-zinc-200 [&_pre]:dark:bg-black/30 [&_pre]:p-3
              [&_code]:font-mono [&_code]:text-[12px] [&_pre_code]:bg-transparent [&_pre_code]:p-0
              [&_blockquote]:border-l-4 [&_blockquote]:border-zinc-400 [&_blockquote]:pl-3 [&_blockquote]:text-zinc-600 [&_blockquote]:dark:text-zinc-400
              [&_hr]:my-3 [&_hr]:border-zinc-300 [&_hr]:dark:border-white/20
              [&_a]:text-emerald-600 [&_a]:dark:text-emerald-400 [&_a]:underline [&_a]:break-all
              [&_strong]:font-semibold
              [&_table]:w-full [&_table]:my-2 [&_table]:border-collapse [&_table]:text-[12px]
              [&_th]:border [&_th]:border-zinc-300 [&_th]:dark:border-white/20 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-semibold [&_th]:bg-zinc-200 [&_th]:dark:bg-white/5
              [&_td]:border [&_td]:border-zinc-300 [&_td]:dark:border-white/20 [&_td]:px-2 [&_td]:py-1
              [&_tr]:border-b [&_tr]:border-zinc-200 [&_tr]:dark:border-white/10"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {message.content}
            </ReactMarkdown>
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