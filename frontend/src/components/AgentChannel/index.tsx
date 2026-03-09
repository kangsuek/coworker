import { useCallback, useEffect, useRef, useState } from 'react'
import { PanelRightClose } from 'lucide-react'

import type { AgentMessage } from '../../types/api'
import AgentMessageCard from './AgentMessage'
import AgentStatusBar from './AgentStatusBar'

const ROLE_PRESETS: { name: string; description: string }[] = [
  { name: 'Researcher', description: '리서치 전문가. 사실에 기반하여 조사하고, 출처를 명시하며, 구조화된 보고서를 작성합니다.' },
  { name: 'Writer', description: '테크니컬 라이터. 주어진 자료를 바탕으로 명확하고 읽기 쉬운 문서를 작성합니다.' },
  { name: 'Planner', description: '프로젝트 플래너. 복잡한 작업을 단계별로 분해하고, 담당자와 산출물을 정의합니다.' },
  { name: 'Coder', description: '시니어 소프트웨어 엔지니어. 클린 코드 작성, 에러 처리, 코드 설명을 제공합니다.' },
  { name: 'Reviewer', description: '코드/문서 리뷰어. 논리적 오류, 개선점, 베스트 프랙티스 위반을 지적하고 대안을 제시합니다.' },
]

interface Props {
  mode: 'solo' | 'team' | null
  messages: AgentMessage[]
  isPolling: boolean
  isRunActive: boolean
  onCloseMobile?: () => void
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
  onCloseMobile,
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

  return (
    <div className="w-full h-full flex flex-col relative overflow-hidden">
      <header className="flex items-center justify-between p-3 border-b border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-950 shrink-0">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <h2 className="text-sm font-bold text-zinc-800 dark:text-zinc-100 shrink-0">Agent Channel</h2>
          <div className="flex items-center gap-1.5 flex-wrap">
            {ROLE_PRESETS.map(({ name, description }) => (
              <span
                key={name}
                title={description}
                className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-600 border border-zinc-200 dark:bg-zinc-800/60 dark:text-zinc-400 dark:border-zinc-700 cursor-help"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 text-xs font-bold text-zinc-500">
            {hasMessages && (
              <>
                <button onClick={handleExportText} className="hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors">TXT</button>
                <button onClick={handleExportJson} className="hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors">JSON</button>
              </>
            )}
          </div>
          {onCloseMobile && (
            <button 
              onClick={onCloseMobile}
              className="p-1.5 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 ml-2"
            >
              <PanelRightClose size={18} />
            </button>
          )}
        </div>
      </header>

      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
        {isTeamActive && hasMessages ? (
          <>
            {messages.map((msg) => (
              <AgentMessageCard key={msg.id} message={msg} />
            ))}
          </>
        ) : isTeamActive && isPolling ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 dark:text-zinc-400">
            <div className="w-3 h-4 bg-emerald-500 animate-pulse mb-3" />
            <p className="text-sm font-mono text-emerald-600 dark:text-emerald-500">&gt; Agent 작업 시작 중...</p>
          </div>
        ) : mode === 'solo' ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 dark:text-zinc-400">
            <div className="w-3 h-4 bg-emerald-500 mb-3" />
            <p className="text-sm font-mono text-emerald-600 dark:text-emerald-500">&gt; Solo 모드</p>
            <p className="text-xs font-mono text-zinc-500 mt-1.5">단독 응답이 처리됩니다.</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-[50vh] text-zinc-500 dark:text-zinc-400">
            <div className="w-3 h-4 bg-emerald-500 animate-pulse mb-3" />
            <p className="text-sm font-mono text-emerald-600 dark:text-emerald-500">&gt; Team 작업이 시작되면</p>
            <p className="text-xs font-mono opacity-70 mt-1.5">Agent 간 대화가 시작됩니다.</p>
          </div>
        )}
        <div ref={messagesEndRef} className="h-2"></div>
      </div>

      {/* 6-6: Agent 요약 표시 (실행 중이거나 메시지 있을 때) */}
      {(hasMessages || isRunActive) && <AgentStatusBar messages={messages} isActive={isRunActive} />}

      {/* 다운로드 완료 토스트 */}
      {toast && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 px-4 py-2 bg-zinc-800 text-white dark:bg-zinc-700 text-xs rounded-lg shadow-lg transition-opacity duration-200">
          ✓ {toast}
        </div>
      )}
    </div>
  )
}
