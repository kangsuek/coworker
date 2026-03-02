import { useCallback, useEffect, useRef, useState } from 'react'

import type { AgentMessage } from '../../types/api'
import AgentMessageCard from './AgentMessage'
import AgentStatusBar from './AgentStatusBar'

interface Props {
  mode: 'solo' | 'team' | null
  messages: AgentMessage[]
  isPolling: boolean
  isRunActive: boolean
  collapsed?: boolean
  onCollapse?: () => void
  onExpand?: () => void
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function AgentChannel({
  mode,
  messages,
  isPolling,
  isRunActive,
  collapsed = false,
  onCollapse,
  onExpand,
}: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showToast = useCallback((message: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    setToast(message)
    toastTimerRef.current = setTimeout(() => setToast(null), 2500)
  }, [])

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  const handleExportText = () => {
    const lines = messages.map((m) => `[${m.sender}]\n${m.content}`)
    const blob = new Blob([lines.join('\n\n---\n\n')], { type: 'text/plain;charset=utf-8' })
    downloadBlob(blob, 'agent-messages.txt')
    showToast('TXT 파일이 다운로드되었습니다')
  }

  const handleExportJson = () => {
    const blob = new Blob([JSON.stringify(messages, null, 2)], {
      type: 'application/json;charset=utf-8',
    })
    downloadBlob(blob, 'agent-messages.json')
    showToast('JSON 파일이 다운로드되었습니다')
  }

  // 새 메시지 도착 시 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const hasMessages = messages.length > 0
  const isTeamActive = mode === 'team' || hasMessages

  if (collapsed) {
    return (
      <div className="w-full min-w-0 min-h-0 h-full flex flex-col bg-[#0D0D0D] dark:bg-[#0D0D0D] shrink-0 relative overflow-hidden">
        <div className="h-8 flex items-center justify-center border-b border-white/10 dark:border-white/10 bg-[#141414] dark:bg-[#141414] shrink-0">
          {onExpand && (
            <button
              type="button"
              onClick={onExpand}
              className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-600 dark:text-gray-400"
              title="Agent Channel 펼치기"
              aria-label="Agent Channel 펼치기"
            >
              <span className="text-lg" aria-hidden>»</span>
            </button>
          )}
        </div>
        <div className="flex-1 flex items-center justify-center p-1">
          {onExpand && (
            <button
              type="button"
              onClick={onExpand}
              className="rounded hover:bg-gray-100 dark:hover:bg-gray-700 p-1.5 text-gray-500 dark:text-gray-400"
              title="Agent Channel 펼치기"
            >
              <span className="text-sm font-medium" style={{ writingMode: 'vertical-rl' }}>
                Agent
              </span>
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 min-h-0 h-full flex flex-col bg-[#0D0D0D] dark:bg-[#0D0D0D] shrink-0 relative overflow-hidden">
      <header className="h-8 pl-4 pr-0 border-b border-white/10 dark:border-white/10 bg-[#141414] dark:bg-[#141414] shrink-0 flex items-center justify-between">
        <span className="font-medium text-gray-200 dark:text-gray-200 truncate min-w-0">Agent Channel</span>
        <div className="flex items-center gap-1 shrink-0">
          {hasMessages && (
            <>
              <button
                onClick={handleExportText}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="텍스트로 내보내기"
              >
                TXT
              </button>
              <button
                onClick={handleExportJson}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="JSON으로 내보내기"
              >
                JSON
              </button>
            </>
          )}
          {onCollapse && (
            <button
              type="button"
              onClick={onCollapse}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-600 dark:text-gray-400"
              title="Agent Channel 접기"
              aria-label="Agent Channel 접기"
            >
              <span className="text-sm" aria-hidden>«</span>
            </button>
          )}
        </div>
      </header>

      {/* 메시지 목록 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4">
        {isTeamActive && hasMessages ? (
          <>
            {messages.map((msg) => (
              <AgentMessageCard key={msg.id} message={msg} />
            ))}
          </>
        ) : isTeamActive && isPolling ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <div className="w-3 h-4 bg-emerald-500 animate-pulse mb-3" />
            <p className="text-sm font-mono text-emerald-500">&gt; Agent 작업 시작 중...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <div className="w-3 h-4 bg-emerald-500 animate-pulse mb-3" />
            <p className="text-sm font-mono text-emerald-500">&gt; Team 작업이 시작되면</p>
            <p className="text-xs font-mono text-gray-500 mt-1.5">Agent 간 대화가 시작됩니다.</p>
            
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 6-6: Agent 요약 표시 */}
      {hasMessages && <AgentStatusBar messages={messages} isActive={isRunActive} />}

      {/* 다운로드 완료 토스트 */}
      {toast && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 px-4 py-2 bg-gray-800 dark:bg-gray-700 text-white text-xs rounded-lg shadow-lg transition-opacity duration-200">
          ✓ {toast}
        </div>
      )}
    </div>
  )
}
