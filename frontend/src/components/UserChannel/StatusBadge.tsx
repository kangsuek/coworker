import type { RunStatusType } from '../../types/api'

interface StatusConfig {
  label: string
  color: string
  dot: string
}

const STATUS_CONFIG: Record<RunStatusType, StatusConfig> = {
  queued: { label: '대기 중', color: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400' },
  thinking: { label: '분석 중...', color: 'bg-blue-100 text-blue-700', dot: 'bg-blue-500' },
  solo: { label: 'Solo 응답 중...', color: 'bg-indigo-100 text-indigo-700', dot: 'bg-indigo-500' },
  delegating: {
    label: '팀 구성 중...',
    color: 'bg-yellow-100 text-yellow-700',
    dot: 'bg-yellow-500',
  },
  working: { label: '작업 중...', color: 'bg-orange-100 text-orange-700', dot: 'bg-orange-500' },
  integrating: {
    label: '통합 중...',
    color: 'bg-purple-100 text-purple-700',
    dot: 'bg-purple-500',
  },
  done: { label: '완료', color: 'bg-green-100 text-green-700', dot: 'bg-green-500' },
  error: { label: '오류', color: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  cancelled: { label: '취소됨', color: 'bg-gray-100 text-gray-500', dot: 'bg-gray-400' },
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
}

export default function StatusBadge({ status, progress, model }: Props) {
  const config = STATUS_CONFIG[status]
  const isAnimated = ANIMATED_STATES.includes(status)
  const modelLabel = shortModelName(model)

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${config.color}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${config.dot} ${isAnimated ? 'animate-pulse' : ''}`}
      />
      {config.label}
      {progress && ` (${progress})`}
      {modelLabel && <span className="opacity-60">· {modelLabel}</span>}
    </span>
  )
}
