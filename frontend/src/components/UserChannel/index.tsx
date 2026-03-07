import { useEffect, useRef, useState } from 'react'
import { Plus, X } from 'lucide-react'

import { api } from '../../lib/api'
import type { RunStatus, Session, UserMessage } from '../../types/api'
import MessageBubble from './MessageBubble'
import StatusBadge from './StatusBadge'

interface Props {
  currentSession: Session | null
  messages: UserMessage[]
  runId: string | null
  runStatus: RunStatus
  soloStreamingContent?: string
  llmProvider?: string
  llmModel?: string
  onMessageAdded: (msg: UserMessage) => void
  onSessionCreated: (sessionId: string) => void
  onModeChange: (mode: 'solo' | 'team' | null) => void
  onRunChange: (runId: string | null) => void
}

export default function UserChannel({
  currentSession,
  messages,
  runId,
  runStatus,
  soloStreamingContent = '',
  llmProvider = 'claude-cli',
  llmModel = '',
  onMessageAdded,
  onSessionCreated,
  onModeChange,
  onRunChange,
}: Props) {
  const [input, setInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const onModeChangeRef = useRef(onModeChange)

  useEffect(() => {
    onModeChangeRef.current = onModeChange
  })

  // mode 감지 시 즉시 알림 (Agent Channel SSE 활성화용)
  useEffect(() => {
    if (runStatus.mode) {
      onModeChangeRef.current(runStatus.mode)
    }
  }, [runStatus.mode])

  // 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, runId, soloStreamingContent])

  const handleSend = async () => {
    const isRunning = submitting || runId !== null
    if (!input.trim() || isRunning) return

    const text = input.trim()
    setInput('')
    setSubmitting(true)

    onMessageAdded({
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      mode: null,
      created_at: new Date().toISOString(),
    })

    try {
      const resp = await api.chat({ 
        session_id: currentSession?.id, 
        message: text,
        llm_provider: llmProvider,
        llm_model: llmModel || null,
      })
      if (!currentSession) {
        onSessionCreated(resp.session_id)
      }
      onRunChange(resp.run_id)
    } catch {
      onMessageAdded({
        id: crypto.randomUUID(),
        role: 'reader',
        content: 'API 오류가 발생했습니다. 서버 연결을 확인해주세요.',
        mode: null,
        created_at: new Date().toISOString(),
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!runId) return
    try {
      await api.cancelRun(runId)
    } catch {
      // 에러 무시 - 폴링이 cancelled 상태를 감지해 처리
    }
  }

  const isRunning = submitting || runId !== null

  return (
    <>
      <div className="flex-1 overflow-y-auto flex flex-col p-4 sm:p-6 lg:px-12 scrollbar-hide">
        <div className="max-w-3xl w-full mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[50vh] text-zinc-500 dark:text-zinc-400">
              <p className="text-sm font-mono text-emerald-600 dark:text-emerald-500 mb-2">&gt; 무엇이든 물어보세요</p>
              <p className="text-xs font-mono opacity-70">복잡한 작업은 Team 모드로 진행할 수 있습니다.</p>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}

          {runId && (
            soloStreamingContent ? (
              <div className="flex justify-start mt-2">
                <div className="px-4 py-3 rounded-xl border bg-zinc-100 border-zinc-200 text-zinc-700 dark:bg-zinc-900/80 dark:border-zinc-800 dark:text-zinc-300 text-[14px] max-w-[85%] sm:max-w-[80%]">
                  <p className="leading-relaxed whitespace-pre-wrap break-words">
                    {soloStreamingContent}
                    <span className="inline-block w-1 h-3.5 bg-zinc-400 dark:bg-zinc-500 ml-0.5 animate-pulse align-middle" />
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex justify-start mt-2">
                <StatusBadge status={runStatus.status} progress={runStatus.progress} model={runStatus.model} timing={runStatus.timing} />
              </div>
            )
          )}

          <div ref={messagesEndRef} className="h-4"></div>
        </div>
      </div>

      <div className="p-4 w-full border-t border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-950 shrink-0">
        <div className="max-w-4xl mx-auto flex gap-2 items-center h-10">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            accept="*/*"
            onChange={(e) => {
              const files = e.target.files
              if (files?.length) {
                // TODO: 파일 첨부 처리 (미리보기/업로드 연동)
                e.target.value = ''
              }
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isRunning}
            className="shrink-0 h-10 w-10 flex items-center justify-center rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="파일 첨부"
          >
            <Plus size={20} strokeWidth={2} />
          </button>
          <div className="flex-1 relative flex items-center h-10 min-h-10 p-1 rounded-xl border transition-all shadow-sm bg-zinc-50 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 focus-within:border-zinc-300 dark:focus-within:border-zinc-700">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="메시지를 입력하세요..."
              className="w-full h-full min-h-0 py-1.5 px-2 bg-transparent resize-none outline-none text-sm leading-tight max-h-32 overflow-y-auto scrollbar-hide text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-600"
              rows={1}
              disabled={isRunning}
            />
          </div>
          
          {isRunning ? (
            <button 
              onClick={handleCancel}
              className="h-10 px-4 rounded-xl shrink-0 transition-all bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 font-medium text-sm flex items-center gap-1.5"
            >
              취소 <X size={16} strokeWidth={2.5} />
            </button>
          ) : (
            <button 
              onClick={handleSend}
              disabled={!input.trim()}
              className={`h-10 px-4 rounded-xl shrink-0 transition-all font-medium text-sm flex items-center
                ${input.trim() 
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md' 
                  : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600'}
              `}
            >
              전송
            </button>
          )}
        </div>
      </div>
    </>
  )
}
