import { useState } from 'react'

import AgentChannel from './components/AgentChannel'
import ErrorBoundary from './components/ErrorBoundary'
import SessionList from './components/SessionList'
import UserChannel from './components/UserChannel'
import { useAgentPolling } from './hooks/useAgentPolling'
import { useSession } from './hooks/useSession'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [currentMode, setCurrentMode] = useState<'solo' | 'team' | null>(null)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const session = useSession()

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
    <div className="flex h-screen bg-gray-50 text-gray-900 overflow-hidden">
      {sidebarOpen && (
        <SessionList
          sessions={session.sessions}
          currentSessionId={session.currentSession?.id ?? null}
          onSwitch={handleSwitchSession}
          onCreate={handleCreateSession}
        />
      )}

      <div className="flex-1 flex min-w-0">
        {/* User Channel */}
        <div className="flex-1 flex flex-col border-r border-gray-200 min-w-0">
          <header className="px-4 py-3 border-b border-gray-200 bg-white flex items-center gap-2 shrink-0">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded hover:bg-gray-100 transition-colors text-gray-600"
              title={sidebarOpen ? '사이드바 닫기' : '사이드바 열기'}
            >
              ☰
            </button>
            <span className="font-medium truncate text-gray-800">
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

        {/* Agent Channel */}
        <ErrorBoundary fallbackLabel="Agent Channel">
          <AgentChannel
            key={session.currentSession?.id ?? 'new'}
            mode={currentMode}
            messages={agentMessages}
            isPolling={isAgentPolling}
            isRunActive={currentRunId !== null}
          />
        </ErrorBoundary>
      </div>
    </div>
  )
}

export default App
