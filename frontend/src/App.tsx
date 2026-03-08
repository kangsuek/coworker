import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react'

import AgentChannel from './components/AgentChannel'
import ErrorBoundary from './components/ErrorBoundary'
import SessionList from './components/SessionList'
import UserChannel from './components/UserChannel'
import { useMemory } from './hooks/useMemory'
import { useRunSSE } from './hooks/useRunSSE'
import { useSession } from './hooks/useSession'
import { api } from './lib/api'
import type { AgentMessage } from './types/api'

const THEME_KEY = 'coworker_theme'

const CLAUDE_MODELS = [
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'haiku', label: 'Haiku' },
  { value: 'opus', label: 'Opus' },
]

const GEMINI_MODELS = [
  { value: 'gemini-3-pro-preview', label: 'Gemini3 pro' },
  { value: 'gemini-3-flash-preview', label: 'Gemini3 flash' },
  { value: 'gemini-2.5-pro', label: 'Gemini2.5 Pro' },
  { value: 'gemini-2.5-flash', label: 'Gemini2.5 Flash' },
]

function getModelOptions(provider: string, currentValue: string): { value: string; label: string }[] {
  const options = provider === 'gemini-cli' ? GEMINI_MODELS : CLAUDE_MODELS
  if (!currentValue) return options
  const exists = options.some((o) => o.value === currentValue)
  if (exists) return options
  return [{ value: currentValue, label: currentValue }, ...options]
}

function loadTheme(): 'light' | 'dark' {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t === 'dark' || t === 'light') return t
  } catch {
    /* ignore */
  }
  return 'dark' // default to dark according to design
}

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(loadTheme)
  const [isSidebarOpen, setIsSidebarOpen] = useState(typeof window !== 'undefined' ? window.innerWidth >= 768 : true)
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)

  useEffect(() => {
    const handleResize = () => {
      setIsSidebarOpen(window.innerWidth >= 768)
      setIsAgentPanelOpen(window.innerWidth >= 1024)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])
  
  const [currentMode, setCurrentMode] = useState<'solo' | 'team' | null>(null)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [historicalAgentMessages, setHistoricalAgentMessages] = useState<AgentMessage[]>([])
  const session = useSession()
  const { memories, addMemory, removeMemory, refreshMemories } = useMemory()

  const [llmProvider, setLlmProvider] = useState('gemini-cli')
  const [llmModel, setLlmModel] = useState('gemini-3-flash-preview')
  const [prevSessionId, setPrevSessionId] = useState<string | undefined>(undefined)

  if (session.currentSession?.id !== prevSessionId) {
    setPrevSessionId(session.currentSession?.id)
    setLlmProvider(session.currentSession?.llm_provider || 'gemini-cli')
    setLlmModel(session.currentSession?.llm_model || (session.currentSession?.llm_provider === 'claude-cli' ? 'haiku' : 'gemini-3-flash-preview'))
  }

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }, [])

  const {
    runStatus: currentRunStatus,
    agentMessages,
    soloStreamingContent,
    isConnected: isSSEConnected,
  } = useRunSSE(currentRunId, {
    onDone: (response, mode, model, timing) => {
      if (mode === 'team' && currentRunId) {
        const runId = currentRunId
        api.getAgentMessages(runId)
          .then(({ messages }) => setHistoricalAgentMessages(messages))
          .catch(() => {})
      }
      // BUG-01: 채팅 트리거로 메모리 저장 후 사이드바 즉시 갱신
      if (response.startsWith('✅ 기억했습니다')) {
        refreshMemories()
      }
      session.addMessage({
        id: crypto.randomUUID(),
        role: 'reader',
        content: response,
        mode,
        model,
        timing,
        created_at: new Date().toISOString(),
      })
      setCurrentMode(mode)
      setCurrentRunId(null)
    },
    onError: (errorResponse) => {
      session.addMessage({
        id: crypto.randomUUID(),
        role: 'reader',
        content: errorResponse || '오류가 발생했습니다. 다시 시도해주세요.',
        mode: null,
        created_at: new Date().toISOString(),
      })
      setCurrentRunId(null)
    },
    onCancelled: () => {
      const doneCount = agentMessages.filter((m) => m.status === 'done').length
      if (currentMode === 'team' && agentMessages.length > 0) {
        if (currentRunId) {
          const runId = currentRunId
          api.getAgentMessages(runId)
            .then(({ messages }) => setHistoricalAgentMessages(messages))
            .catch(() => {})
        }
        session.addMessage({
          id: crypto.randomUUID(),
          role: 'reader',
          content: `${agentMessages.length}개 중 ${doneCount}개 Agent 완료 후 취소되었습니다.`,
          mode: 'team',
          created_at: new Date().toISOString(),
        })
      }
      setCurrentRunId(null)
    },
  })

  const handleSessionCreated = (sessionId: string) => {
    session.setCurrentSessionFromChat(sessionId)
    setTimeout(() => session.refreshSessions(), 1500)
  }

  const handleSwitchSession = async (id: string) => {
    setCurrentRunId(null)
    setCurrentMode(null)
    setHistoricalAgentMessages([])
    const detail = await session.switchSession(id)
    // 마지막 팀 모드 실행의 에이전트 메시지 복원
    const lastTeamMsg = detail.messages.slice().reverse().find(
      (m) => m.role === 'reader' && m.mode === 'team' && m.run_id,
    )
    if (lastTeamMsg?.run_id) {
      api.getAgentMessages(lastTeamMsg.run_id)
        .then(({ messages }) => setHistoricalAgentMessages(messages))
        .catch(() => {})
    }
  }

  const handleCreateSession = () => {
    setCurrentRunId(null)
    setCurrentMode(null)
    setHistoricalAgentMessages([])
    session.createSession()
  }

  const handleDeleteSession = (id: string) => {
    setCurrentRunId(null)
    setCurrentMode(null)
    setHistoricalAgentMessages([])
    session.deleteSession(id)
  }


  // AgentChannel 표시용: 실행 중이면 라이브, 아니면 히스토리
  const displayedAgentMessages = currentRunId !== null ? agentMessages : historicalAgentMessages
  const displayedMode = currentRunId !== null
    ? currentMode
    : historicalAgentMessages.length > 0 ? 'team' : currentMode

  const isDarkMode = theme === 'dark'

  return (
    <div className={`flex h-screen w-full overflow-hidden transition-colors duration-300 ${isDarkMode ? 'bg-zinc-950 text-zinc-100' : 'bg-zinc-50 text-zinc-900'} font-sans`}>
      {/* macOS hiddenInset 타이틀바: 트래픽 라이트 전용 드래그 영역 (fixed, 항상 최상단) */}
      <div
        style={{ WebkitAppRegion: 'drag', height: 40, top: 0, left: 0, right: 0, position: 'fixed', zIndex: 9999 } as React.CSSProperties}
        className={isDarkMode ? 'bg-zinc-900' : 'bg-white'}
      />
      
      {/* Left Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-40 transform transition-all duration-300 ease-in-out overflow-hidden pt-10
        md:relative md:translate-x-0 md:pt-10 shrink-0
        ${isSidebarOpen ? 'w-72 translate-x-0' : 'w-72 -translate-x-full md:w-0 md:border-none'}
        ${isDarkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-zinc-200'}
        border-r
      `}>
        <SessionList
          sessions={session.sessions}
          currentSessionId={session.currentSession?.id ?? null}
          onSwitch={handleSwitchSession}
          onCreate={handleCreateSession}
          onDeleteSession={handleDeleteSession}
          onUpdateTitle={session.updateSessionTitle}
          theme={theme}
          onThemeToggle={toggleTheme}
          onCloseMobile={() => setIsSidebarOpen(false)}
          memories={memories}
          onAddMemory={addMemory}
          onDeleteMemory={removeMemory}
        />
      </div>

      {/* Mobile background overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden backdrop-blur-sm transition-opacity"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main Chat Area */}
      <div className={`flex-1 flex flex-col relative min-w-0 pt-10 ${isDarkMode ? 'bg-zinc-950' : 'bg-zinc-50'}`}>
        {/* Main Header */}
        <header className={`flex items-center justify-between p-3 border-b shrink-0 ${isDarkMode ? 'border-zinc-800/80 bg-zinc-950' : 'border-zinc-200 bg-white'}`}>
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`p-2 -ml-1 rounded-lg transition-colors ${isDarkMode ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-600'}`}
            >
              <Menu size={20} />
            </button>
            <h2 className="text-sm font-semibold truncate max-w-[200px] sm:max-w-xs">
              {session.currentSession?.title ?? '새 대화'}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            {/* Model Selectors */}
            <div className={`hidden sm:flex relative items-center rounded-md border text-xs transition-colors min-w-[5rem] overflow-visible
              ${isDarkMode ? 'border-zinc-800 bg-zinc-900/50' : 'border-zinc-200 bg-white'}
            `}>
              <ChevronDown size={12} className={`absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none z-0 ${isDarkMode ? 'text-zinc-500' : 'text-zinc-400'}`} aria-hidden />
              <select 
                value={llmProvider}
                onChange={(e) => {
                  const provider = e.target.value
                  setLlmProvider(provider)
                  setLlmModel(provider === 'claude-cli' ? 'haiku' : 'gemini-3-flash-preview')
                }}
                className={`relative z-10 appearance-none bg-transparent pl-3 pr-7 py-1.5 font-medium outline-none cursor-pointer w-full min-w-0 ${isDarkMode ? 'text-zinc-300' : 'text-zinc-700'}`}
              >
                <option value="claude-cli">Claude CLI</option>
                <option value="gemini-cli">Gemini CLI</option>
              </select>
            </div>

            <div className={`hidden sm:flex relative items-center rounded-md border text-xs transition-colors min-w-[5rem] overflow-visible
              ${isDarkMode ? 'border-zinc-800 bg-zinc-900/50' : 'border-zinc-200 bg-white'}
            `}>
              <ChevronDown size={12} className={`absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none z-0 ${isDarkMode ? 'text-zinc-500' : 'text-zinc-400'}`} aria-hidden />
              <select 
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className={`relative z-10 appearance-none bg-transparent pl-3 pr-7 py-1.5 font-medium outline-none cursor-pointer w-full min-w-0 ${isDarkMode ? 'text-zinc-300' : 'text-zinc-700'}`}
              >
                {getModelOptions(llmProvider, llmModel).map((opt) => (
                  <option key={opt.value || '__default__'} value={opt.value}>
                    {opt.label || opt.value}
                  </option>
                ))}
              </select>
            </div>
            
            <button
              onClick={() => setIsAgentPanelOpen(!isAgentPanelOpen)}
              className={`p-1.5 rounded-lg transition-colors ml-1 ${isDarkMode ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-600'}`}
              title={isAgentPanelOpen ? "Agent Channel 숨기기" : "Agent Channel 보기"}
            >
              {isAgentPanelOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
            </button>
          </div>
        </header>

        <UserChannel
          key={session.currentSession?.id ?? 'new'}
          currentSession={session.currentSession}
          messages={session.messages}
          runId={currentRunId}
          runStatus={currentRunStatus}
          soloStreamingContent={soloStreamingContent}
          llmProvider={llmProvider}
          llmModel={llmModel}
          onMessageAdded={session.addMessage}
          onSessionCreated={handleSessionCreated}
          onModeChange={setCurrentMode}
          onRunChange={setCurrentRunId}
        />
      </div>

      {/* Right Panel (Agent Channel) */}
      <div className={`
        fixed inset-y-0 right-0 z-40 w-full sm:w-[400px] transform transition-transform duration-300 ease-in-out flex flex-col shrink-0 pt-10
        lg:relative lg:translate-x-0 lg:w-[480px] lg:pt-10
        ${isAgentPanelOpen ? 'translate-x-0' : 'translate-x-full lg:hidden lg:w-0 lg:border-none'}
        ${isDarkMode ? 'bg-zinc-950 border-zinc-800' : 'bg-zinc-50 border-zinc-200'}
        border-l shadow-2xl lg:shadow-none
      `}>
        <ErrorBoundary fallbackLabel="Agent Channel">
          <AgentChannel
            mode={displayedMode}
            messages={displayedAgentMessages}
            isPolling={isSSEConnected}
            isRunActive={currentRunId !== null}
            onCloseMobile={() => setIsAgentPanelOpen(false)}
          />
        </ErrorBoundary>
      </div>

    </div>
  )
}

export default App
