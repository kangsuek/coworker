import { useCallback, useEffect, useState } from 'react'

import AgentChannel from './components/AgentChannel'
import ErrorBoundary from './components/ErrorBoundary'
import SessionList from './components/SessionList'
import Splitbar from './components/Splitbar'
import UserChannel from './components/UserChannel'
import { useAgentPolling } from './hooks/useAgentPolling'
import { useSession } from './hooks/useSession'

const LAYOUT_KEY = 'coworker_layout'
const THEME_KEY = 'coworker_theme'
const MIN_SIDEBAR = 180
const MAX_SIDEBAR = 480
const DEFAULT_SIDEBAR = 256
const SIDEBAR_RAIL = 35
const MIN_AGENT = 320
const MAX_AGENT = 640
const DEFAULT_AGENT = 420
const AGENT_RAIL = 35

function loadLayout(): { sidebar: number; agent: number } {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as { sidebar?: number; agent?: number }
      return {
        sidebar: clamp(parsed.sidebar ?? DEFAULT_SIDEBAR, MIN_SIDEBAR, MAX_SIDEBAR),
        agent: clamp(parsed.agent ?? DEFAULT_AGENT, MIN_AGENT, MAX_AGENT),
      }
    }
  } catch {
    /* ignore */
  }
  return { sidebar: DEFAULT_SIDEBAR, agent: DEFAULT_AGENT }
}

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v))
}

function loadTheme(): 'light' | 'dark' {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t === 'dark' || t === 'light') return t
  } catch {
    /* ignore */
  }
  return 'light'
}

function App() {
  const [layout, setLayout] = useState(loadLayout)
  const [theme, setTheme] = useState<'light' | 'dark'>(loadTheme)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [agentCollapsed, setAgentCollapsed] = useState(false)
  const [currentMode, setCurrentMode] = useState<'solo' | 'team' | null>(null)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const session = useSession()

  useEffect(() => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar: layout.sidebar, agent: layout.agent }))
  }, [layout.sidebar, layout.agent])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }, [])

  const resizeSidebar = useCallback((deltaX: number) => {
    if (sidebarCollapsed) {
      if (deltaX > 0) setSidebarCollapsed(false)
      return
    }
    setLayout((prev) => {
      const next = clamp(prev.sidebar + deltaX, MIN_SIDEBAR, MAX_SIDEBAR)
      return { ...prev, sidebar: next }
    })
    if (deltaX < 0 && layout.sidebar + deltaX < MIN_SIDEBAR) setSidebarCollapsed(true)
  }, [sidebarCollapsed, layout.sidebar])
  const resizeAgent = useCallback((deltaX: number) => {
    if (agentCollapsed) {
      if (deltaX < 0) setAgentCollapsed(false)
      return
    }
    setLayout((prev) => {
      const next = clamp(prev.agent - deltaX, MIN_AGENT, MAX_AGENT)
      return { ...prev, agent: next }
    })
    if (deltaX > 0 && layout.agent - deltaX < MIN_AGENT) setAgentCollapsed(true)
  }, [agentCollapsed, layout.agent])

  // useAgentPolling을 App 레벨에서 실행: 취소 메시지 생성에 활용
  const { messages: agentMessages, isPolling: isAgentPolling } = useAgentPolling(
    currentRunId,
    currentMode,
    true,
  )

  const handleSessionCreated = (sessionId: string) => {
    session.setCurrentSessionFromChat(sessionId)
    setTimeout(() => session.refreshSessions(), 1500)
  }

  const handleSwitchSession = (id: string) => {
    setCurrentRunId(null)
    setCurrentMode(null)
    session.switchSession(id)
  }

  const handleCreateSession = () => {
    setCurrentRunId(null)
    setCurrentMode(null)
    session.createSession()
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100 overflow-hidden">
      {sidebarOpen && (
        <>
          <div
            className="flex flex-col shrink-0 min-h-0 h-full transition-[width] duration-200 ease-out"
            style={{ width: sidebarCollapsed ? SIDEBAR_RAIL : layout.sidebar }}
          >
            <SessionList
              sessions={session.sessions}
              currentSessionId={session.currentSession?.id ?? null}
              onSwitch={handleSwitchSession}
              onCreate={handleCreateSession}
              onDeleteSession={session.deleteSession}
              theme={theme}
              onThemeToggle={toggleTheme}
              collapsed={sidebarCollapsed}
              onCollapse={() => setSidebarCollapsed(true)}
              onExpand={() => setSidebarCollapsed(false)}
            />
          </div>
          <Splitbar onResize={resizeSidebar} />
        </>
      )}

      <div className="flex-1 flex min-w-0 min-h-0 overflow-hidden">
        {/* User Channel */}
        <div className="flex-1 flex flex-col min-h-0 border-r border-gray-200 dark:border-gray-700 min-w-[200px] overflow-hidden">
          <header className="h-8 px-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex items-center gap-2 shrink-0">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-600 dark:text-gray-300"
              title={sidebarOpen ? '사이드바 닫기' : '사이드바 열기'}
            >
              ☰
            </button>
            <span className="font-medium truncate text-gray-800 dark:text-gray-200">
              {session.currentSession?.title ?? '새 대화'}
            </span>
          </header>

          <UserChannel
            key={session.currentSession?.id ?? 'new'}
            currentSession={session.currentSession}
            messages={session.messages}
            runId={currentRunId}
            onMessageAdded={session.addMessage}
            onSessionCreated={handleSessionCreated}
            onModeChange={setCurrentMode}
            onRunChange={setCurrentRunId}
            agentMessages={agentMessages}
          />
        </div>

        <Splitbar onResize={resizeAgent} />

        {/* Agent Channel */}
        <div
          className="flex flex-col shrink-0 min-h-0 h-full overflow-hidden transition-[width] duration-200 ease-out"
          style={{ width: agentCollapsed ? AGENT_RAIL : layout.agent }}
        >
          <ErrorBoundary fallbackLabel="Agent Channel">
            <AgentChannel
              key={session.currentSession?.id ?? 'new'}
              mode={currentMode}
              messages={agentMessages}
              isPolling={isAgentPolling}
              isRunActive={currentRunId !== null}
              collapsed={agentCollapsed}
              onCollapse={() => setAgentCollapsed(true)}
              onExpand={() => setAgentCollapsed(false)}
            />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}

export default App
