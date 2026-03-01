import type { Session } from '../../types/api'

interface Props {
  sessions: Session[]
  currentSessionId: string | null
  onSwitch: (id: string) => void
  onCreate: () => void
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

export default function SessionList({ sessions, currentSessionId, onSwitch, onCreate }: Props) {
  return (
    <aside className="w-64 border-r border-gray-200 bg-white flex flex-col shrink-0">
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-gray-900">Coworker</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="text-sm text-gray-400 px-3 py-4 text-center">세션이 없습니다</p>
        ) : (
          sessions.map((sess) => (
            <button
              key={sess.id}
              onClick={() => onSwitch(sess.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg mb-0.5 transition-colors ${
                sess.id === currentSessionId
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <span
                className={`block truncate text-sm font-medium ${
                  sess.id === currentSessionId ? 'text-blue-700' : 'text-gray-800'
                }`}
              >
                {sess.title ?? '새 대화'}
              </span>
              <span className="block text-xs text-gray-400 mt-0.5">
                {formatDate(sess.updated_at)}
              </span>
            </button>
          ))
        )}
      </div>

      <div className="p-2 border-t border-gray-200">
        <button
          onClick={onCreate}
          className="w-full py-2 px-3 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          + 새 세션
        </button>
      </div>
    </aside>
  )
}
