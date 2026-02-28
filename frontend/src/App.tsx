import { useState } from 'react'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      {/* Session Sidebar */}
      {sidebarOpen && (
        <aside className="w-64 border-r border-gray-200 bg-white flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h1 className="text-lg font-bold">Coworker</h1>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            <p className="text-sm text-gray-400 p-2">세션 목록 (Sprint 4)</p>
          </div>
          <div className="p-2 border-t border-gray-200">
            <button className="w-full py-2 px-3 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
              + 새 세션
            </button>
          </div>
        </aside>
      )}

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* User Channel */}
        <div className="flex-1 flex flex-col border-r border-gray-200">
          <header className="px-4 py-3 border-b border-gray-200 bg-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-1.5 rounded hover:bg-gray-100 transition-colors"
              >
                ☰
              </button>
              <span className="font-medium">User Channel</span>
            </div>
          </header>
          <div className="flex-1 overflow-y-auto p-4">
            <p className="text-center text-gray-400 mt-20">
              메시지를 입력하세요 (Sprint 4)
            </p>
          </div>
          <div className="p-4 border-t border-gray-200 bg-white">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="메시지를 입력하세요..."
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled
              />
              <button
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                disabled
              >
                전송
              </button>
            </div>
          </div>
        </div>

        {/* Agent Channel */}
        <div className="w-[420px] flex flex-col bg-gray-50/80">
          <header className="px-4 py-3 border-b border-gray-200 bg-white">
            <span className="font-medium">Agent Channel</span>
          </header>
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <p className="text-2xl mb-2">🤖</p>
              <p className="text-sm">대기 중</p>
              <p className="text-xs mt-1">Team 작업이 시작되면</p>
              <p className="text-xs">Agent 간 대화가 표시됩니다</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
