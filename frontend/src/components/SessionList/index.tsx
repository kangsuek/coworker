import type { Session } from '../../types/api'

interface Props {
  sessions: Session[]
  currentSessionId: string | null
  onSwitch: (id: string) => void
  onCreate: () => void
  onDeleteSession: (id: string) => void
  theme: 'light' | 'dark'
  onThemeToggle: () => void
  collapsed: boolean
  onCollapse: () => void
  onExpand: () => void
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return '오늘'
  if (diffDays === 1) return '어제'
  return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
}

export default function SessionList({
  sessions,
  currentSessionId,
  onSwitch,
  onCreate,
  onDeleteSession,
  theme,
  onThemeToggle,
  collapsed,
  onCollapse,
  onExpand,
}: Props) {
  if (collapsed) {
    return (
      <aside className="w-full min-w-0 min-h-0 h-full border-r border-gray-200 dark:border-white/10 bg-white dark:bg-[#141414] flex flex-col shrink-0 overflow-hidden">
        <div className="h-8 flex items-center justify-center border-b border-gray-200 dark:border-white/10 shrink-0">
          <button
            type="button"
            onClick={onExpand}
            className="p-2 rounded hover:bg-gray-100 dark:hover:bg-white/5 transition-colors text-gray-600 dark:text-gray-400"
            title="세션 목록 펼치기"
            aria-label="세션 목록 펼치기"
          >
            <span className="text-lg" aria-hidden>«</span>
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-1">
          <button
            type="button"
            onClick={onExpand}
            className="rounded hover:bg-gray-100 dark:hover:bg-white/5 p-1.5 text-gray-500 dark:text-gray-400"
            title="세션 목록 펼치기"
          >
            <span className="text-sm font-medium" style={{ writingMode: 'vertical-rl' }}>
              세션
            </span>
          </button>
        </div>
      </aside>
    )
  }

  return (
    <aside className="w-full min-w-0 min-h-0 h-full border-r border-gray-200 dark:border-white/10 bg-white dark:bg-[#141414] flex flex-col shrink-0 overflow-hidden">
      <div className="h-8 flex items-center justify-between gap-2 pl-4 pr-0 border-b border-gray-200 dark:border-white/10 shrink-0">
        <h1 className="text-lg font-bold text-gray-800 dark:text-gray-200 truncate min-w-0 flex-1">
          Coworker
        </h1>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onThemeToggle}
            className="h-6 w-6 flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-white/5 transition-colors text-gray-600 dark:text-gray-400"
            title={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
            aria-label={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
          >
            {theme === 'light' ? (
              <span className="text-sm leading-none inline-flex items-center" aria-hidden>🌙</span>
            ) : (
              <span className="text-sm leading-none inline-flex items-center" aria-hidden>☀️</span>
            )}
          </button>
          <button
            type="button"
            onClick={onCollapse}
            className="h-6 w-6 flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-white/5 transition-colors text-gray-600 dark:text-gray-400"
            title="세션 목록 접기"
            aria-label="세션 목록 접기"
          >
            <span className="text-sm leading-none inline-flex items-center" aria-hidden>»</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-500 px-3 py-4 text-center">
            세션이 없습니다
          </p>
        ) : (
          sessions.map((sess) => (
            <div
              key={sess.id}
              className={`flex items-center gap-1 rounded-sm mb-0 border border-transparent ${
                sess.id === currentSessionId
                  ? 'bg-emerald-50 dark:bg-white/5 border-l-2 border-l-emerald-500 rounded-none'
                  : 'hover:bg-gray-100 dark:hover:bg-white/5'
              }`}
            >
              <button
                type="button"
                onClick={() => onSwitch(sess.id)}
                className={`flex-1 min-w-0 text-left px-2 py-1.5 transition-colors rounded-l-lg ${
                  sess.id === currentSessionId
                    ? 'text-emerald-600 dark:text-emerald-500'
                    : 'text-gray-700 dark:text-gray-300'
                }`}
              >
                <span
                  className={`block truncate text-sm font-medium ${
                    sess.id === currentSessionId
                      ? 'text-emerald-600 dark:text-emerald-500'
                      : 'text-gray-800 dark:text-gray-300'
                  }`}
                >
                  {sess.title ?? '새 대화'}
                </span>
                <span className="block text-xs text-gray-500 dark:text-gray-500 mt-0.5">
                  {formatDate(sess.updated_at)}
                </span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSession(sess.id)
                }}
                className="h-6 w-6 flex items-center justify-center rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-600 dark:hover:text-red-400 shrink-0 mr-1 transition-colors"
                title="세션 삭제"
                aria-label="세션 삭제"
              >
                <span className="text-xs leading-none" aria-hidden>🗑</span>
              </button>
            </div>
          ))
        )}
      </div>

      <div className="h-10 flex items-center px-3 py-1.5 border-t border-gray-200 dark:border-white/10 shrink-0">
        <button
          onClick={onCreate}
          className="w-full py-1.5 px-2 bg-emerald-600 dark:bg-emerald-600 text-white rounded-sm text-xs font-mono font-medium hover:bg-emerald-700 dark:hover:bg-emerald-700 transition-colors"
        >
          + 새 세션
        </button>
      </div>
    </aside>
  )
}
