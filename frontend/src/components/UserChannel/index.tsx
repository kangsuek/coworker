import { useEffect, useRef, useState } from 'react'

import { useRunPolling } from '../../hooks/useRunPolling'
import { api } from '../../lib/api'
import type { Session, UserMessage } from '../../types/api'
import MessageBubble from './MessageBubble'
import StatusBadge from './StatusBadge'

interface Props {
  currentSession: Session | null
  messages: UserMessage[]
  onMessageAdded: (msg: UserMessage) => void
  onSessionCreated: (sessionId: string) => void
  onModeChange: (mode: 'solo' | 'team' | null) => void
}

export default function UserChannel({
  currentSession,
  messages,
  onMessageAdded,
  onSessionCreated,
  onModeChange,
}: Props) {
  const [input, setInput] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const onMessageAddedRef = useRef(onMessageAdded)
  const onModeChangeRef = useRef(onModeChange)
  useEffect(() => {
    onMessageAddedRef.current = onMessageAdded
    onModeChangeRef.current = onModeChange
  })

  const runStatus = useRunPolling(runId, {
    onDone: (response, mode) => {
      onMessageAddedRef.current({
        id: crypto.randomUUID(),
        role: 'reader',
        content: response,
        mode,
        created_at: new Date().toISOString(),
      })
      onModeChangeRef.current(mode)
      setRunId(null)
      setSending(false)
    },
    onError: (errorResponse) => {
      onMessageAddedRef.current({
        id: crypto.randomUUID(),
        role: 'reader',
        content: errorResponse || '오류가 발생했습니다. 다시 시도해주세요.',
        mode: null,
        created_at: new Date().toISOString(),
      })
      setRunId(null)
      setSending(false)
    },
    onCancelled: () => {
      setRunId(null)
      setSending(false)
    },
  })

  // 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, runId])

  const handleSend = async () => {
    if (!input.trim() || sending) return

    const text = input.trim()
    setInput('')
    setSending(true)

    onMessageAdded({
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      mode: null,
      created_at: new Date().toISOString(),
    })

    try {
      const resp = await api.chat({ session_id: currentSession?.id, message: text })
      if (!currentSession) {
        onSessionCreated(resp.session_id)
      }
      setRunId(resp.run_id)
    } catch {
      onMessageAdded({
        id: crypto.randomUUID(),
        role: 'reader',
        content: 'API 오류가 발생했습니다. 서버 연결을 확인해주세요.',
        mode: null,
        created_at: new Date().toISOString(),
      })
      setSending(false)
    }
  }

  const isRunning = sending && runId !== null

  return (
    <>
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <p className="text-lg mb-1">무엇이든 물어보세요</p>
            <p className="text-sm">복잡한 작업은 Team 모드로 자동 전환됩니다</p>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}

        {runId && (
          <div className="flex justify-start mb-4">
            <StatusBadge status={runStatus.status} progress={runStatus.progress} />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-gray-200 bg-white shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="메시지를 입력하세요..."
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm disabled:bg-gray-50"
            disabled={isRunning}
          />
          <button
            onClick={handleSend}
            disabled={isRunning || !input.trim()}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 text-sm font-medium"
          >
            {isRunning ? '...' : '전송'}
          </button>
        </div>
      </div>
    </>
  )
}
