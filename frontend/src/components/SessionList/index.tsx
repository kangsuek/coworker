import { Sun, Moon, Trash2, Plus, X } from 'lucide-react'
import type { Session } from '../../types/api'

interface Props {
  sessions: Session[]
  currentSessionId: string | null
  onSwitch: (id: string) => void
  onCreate: () => void
  onDeleteSession: (id: string) => void
  theme: 'light' | 'dark'
  onThemeToggle: () => void
  onCloseMobile?: () => void
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
  onCloseMobile,
}: Props) {
  const isDarkMode = theme === 'dark'

  return (
    <div className="w-full h-full flex flex-col">
      {/* Sidebar Header */}
      <div className="flex items-center justify-between p-4 border-b border-transparent">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight">Coworker</h1>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={onThemeToggle}
            className={`p-2 rounded-full transition-colors ${isDarkMode ? 'hover:bg-zinc-800 text-yellow-500' : 'hover:bg-zinc-100 text-yellow-600'}`}
            title={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
          >
            {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          {onCloseMobile && (
            <button 
              onClick={onCloseMobile}
              className="lg:hidden p-2 rounded-full hover:bg-zinc-800 text-zinc-400"
              title="사이드바 닫기"
            >
              <X size={20} />
            </button>
          )}
        </div>
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-hide">
        {sessions.map((chat) => {
          const isActive = chat.id === currentSessionId
          return (
            <div 
              key={chat.id}
              onClick={() => onSwitch(chat.id)}
              className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all
                ${isActive && isDarkMode ? 'bg-emerald-900/20 border border-emerald-500/30' : ''}
                ${isActive && !isDarkMode ? 'bg-emerald-50 border border-emerald-200' : ''}
                ${!isActive && isDarkMode ? 'hover:bg-zinc-800/50 border border-transparent' : ''}
                ${!isActive && !isDarkMode ? 'hover:bg-zinc-100 border border-transparent' : ''}
              `}
            >
              <div className="flex-1 min-w-0 pr-2">
                <p className={`text-sm font-medium truncate ${isActive ? 'text-emerald-500' : isDarkMode ? 'text-zinc-300 group-hover:text-white' : 'text-zinc-700 group-hover:text-black'}`}>
                  {chat.title || '새 대화'}
                </p>
                <p className={`text-xs mt-1 ${isDarkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {formatDate(chat.updated_at)}
                </p>
              </div>
              <button 
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSession(chat.id)
                }}
                className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-md transition-all
                ${isDarkMode ? 'hover:bg-zinc-700 text-zinc-500 hover:text-red-400' : 'hover:bg-zinc-200 text-zinc-400 hover:text-red-500'}
              `}>
                <Trash2 size={16} />
              </button>
            </div>
          )
        })}
      </div>

      {/* New Session Button */}
      <div className="p-4 mt-auto">
        <button 
          onClick={onCreate}
          className="w-full h-10 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-[0.98] bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/20"
        >
          <Plus size={18} />
          새 세션
        </button>
      </div>
    </div>
  )
}
