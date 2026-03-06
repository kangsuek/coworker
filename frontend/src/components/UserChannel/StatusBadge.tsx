import { useEffect, useState } from 'react'

import type { RunStatusType, TimingInfo } from '../../types/api'

interface StatusConfig {
  label: string
  color: string
  dot: string
}

const STATUS_CONFIG: Record<RunStatusType, StatusConfig> = {
  queued: { label: '대기 중', color: 'border-gray-500/30 bg-gray-500/10 text-gray-500 dark:border-gray-500/30 dark:bg-gray-500/10 dark:text-gray-400', dot: 'bg-gray-500' },
  thinking: { label: '분석 중...', color: 'border-blue-500/30 bg-blue-500/10 text-blue-600 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-400', dot: 'bg-blue-500' },
  solo: { label: 'Solo 응답 중...', color: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-400', dot: 'bg-indigo-500' },
  delegating: {
    label: '팀 구성 중...',
    color: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-600 dark:border-yellow-500/30 dark:bg-yellow-500/10 dark:text-yellow-400',
    dot: 'bg-yellow-500',
  },
  working: { label: '작업 중...', color: 'border-orange-500/30 bg-orange-500/10 text-orange-600 dark:border-orange-500/30 dark:bg-orange-500/10 dark:text-orange-400', dot: 'bg-orange-500' },
  integrating: {
    label: '통합 중...',
    color: 'border-purple-500/30 bg-purple-500/10 text-purple-600 dark:border-purple-500/30 dark:bg-purple-500/10 dark:text-purple-400',
    dot: 'bg-purple-500',
  },
  done: { label: '완료', color: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400', dot: 'bg-emerald-500' },
  error: { label: '오류', color: 'border-red-500/30 bg-red-500/10 text-red-600 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400', dot: 'bg-red-500' },
  cancelled: { label: '취소됨', color: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-500 dark:border-zinc-500/30 dark:bg-zinc-500/10 dark:text-zinc-400', dot: 'bg-zinc-500' },
}

const ANIMATED_STATES: RunStatusType[] = ['thinking', 'solo', 'delegating', 'working', 'integrating']

function shortModelName(model: string | null | undefined): string | null {
  if (!model) return null
  if (model.includes('haiku')) return 'Haiku'
  if (model.includes('sonnet')) return 'Sonnet'
  if (model.includes('opus')) return 'Opus'
  return model
}

interface Props {
  status: RunStatusType
  progress?: string | null
  model?: string | null
  timing?: TimingInfo | null
}

export default function StatusBadge({ status, progress, model, timing }: Props) {
  const config = STATUS_CONFIG[status]
  const isAnimated = ANIMATED_STATES.includes(status)
  const modelLabel = shortModelName(model)

  let startDate: Date | null = null
  if (status === 'thinking' && timing?.thinking_started_at) {
    startDate = new Date(timing.thinking_started_at)
  } else if (status === 'solo' && timing?.cli_started_at) {
    startDate = new Date(timing.cli_started_at)
  }

  const [now, setNow] = useState<number | null>(null)

  const startTimeMs = startDate?.getTime()

  useEffect(() => {
    if (!startTimeMs) return
    const id = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(id)
  }, [startTimeMs])

  const elapsedSec = startDate && now ? (now - startDate.getTime()) / 1000 : null

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border ${config.color} text-sm font-medium shadow-sm`}>
      <span className={`w-2 h-2 rounded-full ${config.dot} ${isAnimated ? 'animate-pulse' : ''}`} />
      {config.label}
      {progress && ` (${progress})`}
      {elapsedSec !== null && (
        <span className="opacity-70 ml-1 text-xs">{elapsedSec.toFixed(1)}s</span>
      )}
      {modelLabel && <span className="opacity-70 text-xs ml-1 font-mono">{modelLabel}</span>}
    </div>
  )
}
