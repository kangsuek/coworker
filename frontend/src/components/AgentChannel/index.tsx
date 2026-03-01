import { useCallback, useEffect, useRef, useState } from 'react'

import type { AgentMessage } from '../../types/api'
import AgentMessageCard from './AgentMessage'
import AgentStatusBar from './AgentStatusBar'

interface Props {
  mode: 'solo' | 'team' | null
  messages: AgentMessage[]
  isPolling: boolean
  isRunActive: boolean
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function AgentChannel({ mode, messages, isPolling, isRunActive }: Props) {
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

  return (
    <div className="w-[420px] flex flex-col bg-gray-50/80 shrink-0 relative">
      <header className="px-4 py-3 border-b border-gray-200 bg-white shrink-0 flex items-center justify-between">
        <span className="font-medium text-gray-800">Agent Channel</span>
        {/* 6-7: 내보내기 버튼 */}
        {hasMessages && (
          <div className="flex gap-1">
            <button
              onClick={handleExportText}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
              title="텍스트로 내보내기"
            >
              TXT
            </button>
            <button
              onClick={handleExportJson}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
              title="JSON으로 내보내기"
            >
              JSON
            </button>
          </div>
        )}
      </header>

      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto p-4">
        {isTeamActive && hasMessages ? (
          <>
            {messages.map((msg) => (
              <AgentMessageCard key={msg.id} message={msg} />
            ))}
          </>
        ) : isTeamActive && isPolling ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <p className="text-2xl mb-2">⚙️</p>
            <p className="text-sm">Agent 작업 시작 중...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <p className="text-3xl mb-3">🤖</p>
            <p className="text-sm font-medium">대기 중</p>
            <p className="text-xs mt-1.5 text-gray-300">Team 작업이 시작되면</p>
            <p className="text-xs text-gray-300">Agent 간 대화가 표시됩니다</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 6-6: Agent 요약 표시 */}
      {hasMessages && <AgentStatusBar messages={messages} isActive={isRunActive} />}

      {/* 다운로드 완료 토스트 */}
      {toast && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 px-4 py-2 bg-gray-800 text-white text-xs rounded-lg shadow-lg transition-opacity duration-200">
          ✓ {toast}
        </div>
      )}
    </div>
  )
}
