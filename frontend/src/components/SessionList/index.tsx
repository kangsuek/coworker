import { Sun, Moon, Trash2, Plus, X, Pencil, Check, Brain, ChevronDown, ChevronUp } from 'lucide-react'
import { useRef, useState } from 'react'
import type { Memory, Session } from '../../types/api'

interface Props {
  sessions: Session[]
  currentSessionId: string | null
  onSwitch: (id: string) => void
  onCreate: () => void
  onDeleteSession: (id: string) => void
  onUpdateTitle: (id: string, title: string) => void
  theme: 'light' | 'dark'
  onThemeToggle: () => void
  onCloseMobile?: () => void
  memories: Memory[]
  onAddMemory: (content: string) => Promise<void>
  onDeleteMemory: (id: string) => Promise<void>
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const time = date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  if (dateOnly.getTime() === today.getTime()) return `오늘 ${time}`
  if (dateOnly.getTime() === yesterday.getTime()) return `어제 ${time}`
  return date.toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }) + ` ${time}`
}

export default function SessionList({
  sessions,
  currentSessionId,
  onSwitch,
  onCreate,
  onDeleteSession,
  onUpdateTitle,
  theme,
  onThemeToggle,
  onCloseMobile,
  memories,
  onAddMemory,
  onDeleteMemory,
}: Props) {
  const isDarkMode = theme === 'dark'
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [memoryInput, setMemoryInput] = useState('')
  const memoryInputRef = useRef<HTMLInputElement>(null)

  const handleAddMemory = async () => {
    const content = memoryInput.trim()
    if (!content) return
    setMemoryInput('')
    await onAddMemory(content)
  }

  const startEdit = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation()
    setEditingId(session.id)
    setEditingTitle(session.title ?? '')
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const commitEdit = (id: string) => {
    onUpdateTitle(id, editingTitle)
    setEditingId(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === 'Enter') commitEdit(id)
    if (e.key === 'Escape') setEditingId(null)
  }

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
          const isEditing = editingId === chat.id
          return (
            <div
              key={chat.id}
              onClick={() => !isEditing && onSwitch(chat.id)}
              className={`group flex items-center justify-between p-3 rounded-xl transition-all
                ${!isEditing ? 'cursor-pointer' : ''}
                ${isActive && isDarkMode ? 'bg-emerald-900/20 border border-emerald-500/30' : ''}
                ${isActive && !isDarkMode ? 'bg-emerald-50 border border-emerald-200' : ''}
                ${!isActive && isDarkMode ? 'hover:bg-zinc-800/50 border border-transparent' : ''}
                ${!isActive && !isDarkMode ? 'hover:bg-zinc-100 border border-transparent' : ''}
              `}
            >
              <div className="flex-1 min-w-0 pr-1">
                {isEditing ? (
                  <input
                    ref={inputRef}
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onBlur={() => commitEdit(chat.id)}
                    onKeyDown={(e) => handleKeyDown(e, chat.id)}
                    onClick={(e) => e.stopPropagation()}
                    placeholder="세션 제목 입력..."
                    className={`w-full text-sm font-medium rounded px-1 py-0.5 outline-none border
                      ${isDarkMode ? 'bg-zinc-800 border-emerald-500/50 text-zinc-100' : 'bg-white border-emerald-400 text-zinc-900'}
                    `}
                  />
                ) : (
                  <p className={`text-sm font-medium truncate ${isActive ? 'text-emerald-500' : isDarkMode ? 'text-zinc-300 group-hover:text-white' : 'text-zinc-700 group-hover:text-black'}`}>
                    {chat.title || '새 대화'}
                  </p>
                )}
                <p className={`text-xs mt-1 ${isDarkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {formatDate(chat.updated_at)}
                </p>
              </div>
              <div className="flex items-center gap-0.5 shrink-0">
                {isEditing ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); commitEdit(chat.id) }}
                    className={`p-1.5 rounded-md ${isDarkMode ? 'text-emerald-400 hover:bg-zinc-700' : 'text-emerald-600 hover:bg-zinc-200'}`}
                  >
                    <Check size={14} />
                  </button>
                ) : (
                  <>
                    <button
                      onClick={(e) => startEdit(e, chat)}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-md transition-all
                        ${isDarkMode ? 'hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300' : 'hover:bg-zinc-200 text-zinc-400 hover:text-zinc-600'}
                      `}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); onDeleteSession(chat.id) }}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-md transition-all
                        ${isDarkMode ? 'hover:bg-zinc-700 text-zinc-500 hover:text-red-400' : 'hover:bg-zinc-200 text-zinc-400 hover:text-red-500'}
                      `}
                    >
                      <Trash2 size={14} />
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Memory Panel */}
      <div className={`border-t shrink-0 ${isDarkMode ? 'border-zinc-800' : 'border-zinc-200'}`}>
        <button
          onClick={() => setMemoryOpen((v) => !v)}
          className={`w-full flex items-center justify-between px-4 py-3 text-sm font-semibold transition-colors
            ${isDarkMode ? 'text-zinc-400 hover:text-zinc-200' : 'text-zinc-500 hover:text-zinc-800'}
          `}
        >
          <span className="flex items-center gap-2">
            <Brain size={15} />
            전역 메모리
            {memories.length > 0 && (
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold
                ${isDarkMode ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}
              `}>
                {memories.length}
              </span>
            )}
          </span>
          {memoryOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>

        {memoryOpen && (
          <div className="px-3 pb-3 space-y-2">
            {/* 메모리 목록 */}
            {memories.length > 0 ? (
              <div className={`rounded-lg border divide-y max-h-40 overflow-y-auto scrollbar-hide
                ${isDarkMode ? 'border-zinc-700 divide-zinc-700' : 'border-zinc-200 divide-zinc-200'}
              `}>
                {memories.map((mem) => (
                  <div key={mem.id} className="flex items-start gap-2 px-3 py-2 group">
                    <p className={`flex-1 text-xs leading-relaxed break-words min-w-0
                      ${isDarkMode ? 'text-zinc-300' : 'text-zinc-700'}
                    `}>
                      {mem.content}
                    </p>
                    <button
                      onClick={() => onDeleteMemory(mem.id)}
                      className={`shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded transition-all
                        ${isDarkMode ? 'text-zinc-500 hover:text-red-400' : 'text-zinc-400 hover:text-red-500'}
                      `}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className={`text-xs px-1 ${isDarkMode ? 'text-zinc-600' : 'text-zinc-400'}`}>
                저장된 메모리가 없습니다.
              </p>
            )}

            {/* 메모리 추가 입력 */}
            <div className={`flex gap-1.5 rounded-lg border p-1
              ${isDarkMode ? 'border-zinc-700 bg-zinc-900' : 'border-zinc-200 bg-zinc-50'}
            `}>
              <input
                ref={memoryInputRef}
                value={memoryInput}
                onChange={(e) => setMemoryInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddMemory() }}
                placeholder="기억할 내용..."
                className={`flex-1 text-xs bg-transparent outline-none px-1
                  ${isDarkMode ? 'text-zinc-200 placeholder:text-zinc-600' : 'text-zinc-800 placeholder:text-zinc-400'}
                `}
              />
              <button
                onClick={handleAddMemory}
                disabled={!memoryInput.trim()}
                className={`shrink-0 px-2 py-1 rounded-md text-xs font-medium transition-colors
                  ${memoryInput.trim()
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                    : isDarkMode ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed' : 'bg-zinc-200 text-zinc-400 cursor-not-allowed'}
                `}
              >
                추가
              </button>
            </div>
          </div>
        )}
      </div>

      {/* New Session Button */}
      <div className="p-4">
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
