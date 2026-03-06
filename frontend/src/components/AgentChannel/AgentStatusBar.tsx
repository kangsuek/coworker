import { useEffect, useState } from 'react'

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

  useEffect(() => {
    // isActive가 false가 되면 interval을 시작하지 않아 elapsed 자연 고정
    if (!isActive) return
    const interval = setInterval(() => setElapsed(Date.now() - startTime), 1000)
    return () => clearInterval(interval)
  }, [isActive, startTime])

  if (messages.length === 0) return null

  const total = messages.length
  const done = messages.filter((m) => m.status === 'done').length

  return (
    <div className="p-3 text-xs flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800/80 bg-zinc-100 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400 shrink-0">
      <div className="font-medium">{total}개 Agent</div>
      <div className="flex items-center gap-4">
        <span>{done}/{total} 완료</span>
        <span>소요 시간: <span className="text-zinc-800 dark:text-zinc-300">{formatElapsed(elapsed)}</span></span>
      </div>
    </div>
  )
}
