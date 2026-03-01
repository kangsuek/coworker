import { useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import type { AgentMessage } from '../types/api'

export function useAgentPolling(
  runId: string | null,
  mode: 'solo' | 'team' | null,
  isVisible: boolean,
): { messages: AgentMessage[]; isPolling: boolean } {
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const clearTimer = () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }

    if (!runId || mode !== 'team' || !isVisible) {
      clearTimer()
      return
    }

    let cancelled = false

    const tick = async () => {
      if (cancelled) return
      try {
        const data = await api.getAgentMessages(runId)
        // 각 fetch 결과로 전체 메시지 덮어쓰기 (새 run 자동 초기화)
        if (!cancelled) setMessages(data.messages)
      } catch {
        // 일시적 오류 무시, 폴링 계속
      }
      if (!cancelled) {
        const delay = 2000 + Math.random() * 600 - 300
        timerRef.current = setTimeout(tick, delay)
      }
    }

    // 즉시 첫 fetch 후 주기적 폴링
    void tick()

    return () => {
      cancelled = true
      clearTimer()
    }
  }, [runId, mode, isVisible])

  // isPolling: 상태 대신 파생값 (동기 setState in effect 회피)
  const isPolling = !!(runId && mode === 'team' && isVisible)

  return { messages, isPolling }
}
