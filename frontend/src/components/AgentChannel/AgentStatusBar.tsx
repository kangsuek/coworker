import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import type { AgentMessage } from '../../types/api'

interface Props {
  messages: AgentMessage[]
  isActive: boolean
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}초`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return secs > 0 ? `${minutes}분 ${secs}초` : `${minutes}분`
}

export default function AgentStatusBar({ messages, isActive }: Props) {
  const [startTime] = useState(() => Date.now())
  const [elapsed, setElapsed] = useState(0)
  const [activeCliCount, setActiveCliCount] = useState(0)

  useEffect(() => {
    if (!isActive) return
    const interval = setInterval(() => setElapsed(Date.now() - startTime), 1000)
    return () => clearInterval(interval)
  }, [isActive, startTime])

  useEffect(() => {
    const fetchCount = () => {
      api.getCliStatus()
        .then((data) => setActiveCliCount(data.active_cli_count))
        .catch(() => {})
    }
    fetchCount()
    const interval = setInterval(fetchCount, 2000)
    return () => clearInterval(interval)
  }, [])

  if (messages.length === 0 && !isActive) return null

  const total = messages.length
  const done = messages.filter((m) => m.status === 'done').length

  return (
    <div className="p-3 text-xs flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800/80 bg-zinc-100 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400 shrink-0">
      <div className="flex items-center gap-3">
        {total > 0 && <span className="font-medium">{total}개 Agent</span>}
        <span className="flex items-center gap-1.5">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${activeCliCount > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`}
          />
          <span>CLI <span className="text-zinc-800 dark:text-zinc-300 font-medium">{activeCliCount}</span>개 실행 중</span>
        </span>
      </div>
      {total > 0 && (
        <div className="flex items-center gap-4">
          <span>{done}/{total} 완료</span>
          <span>소요 시간: <span className="text-zinc-800 dark:text-zinc-300">{formatElapsed(elapsed)}</span></span>
        </div>
      )}
    </div>
  )
}
