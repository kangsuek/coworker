/**
 * useRunSSE — SSE 기반 실시간 스트리밍 훅
 *
 * /api/runs/{run_id}/stream 엔드포인트를 구독하여
 * run 상태(status/progress)와 에이전트 메시지(content 스트리밍)를
 * 단일 EventSource 연결로 실시간 수신한다.
 *
 * 연결 오류 시 지수 백오프로 자동 재연결한다.
 * Terminal 상태(done/error/cancelled) 도달 시 폴링 API로 최종 응답을 가져온다.
 */
import { useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import type { AgentMessage, RunStatus, RunStatusType, TimingInfo } from '../types/api'

const TERMINAL_STATES: RunStatusType[] = ['done', 'error', 'cancelled']

export const DEFAULT_RUN_STATUS: RunStatus = {
  status: 'queued',
  progress: null,
  response: null,
  mode: null,
  model: null,
  agents: null,
  timing: null,
}

export interface RunSSECallbacks {
  onDone?: (
    response: string,
    mode: 'solo' | 'team' | null,
    model: string | null,
    timing: TimingInfo | null,
  ) => void
  onError?: (errorResponse: string | null) => void
  onCancelled?: () => void
}

interface SSEEvent {
  type: 'connected' | 'status' | 'content' | 'agent_message_created' | 'agent_status_changed'
  run_id?: string
  // status 이벤트 필드
  status?: string
  progress?: string | null
  mode?: 'solo' | 'team' | null
  finished_at?: string | null
  // content 이벤트 필드
  agent?: string
  content?: string
  // agent_message_created 이벤트 필드
  agent_message?: AgentMessage
  // agent_status_changed 이벤트 필드
  agent_message_id?: string
}

const MAX_RECONNECT_DELAY = 16000
const INITIAL_RECONNECT_DELAY = 1000

export function useRunSSE(runId: string | null, callbacks?: RunSSECallbacks) {
  const [runStatus, setRunStatus] = useState<RunStatus>(DEFAULT_RUN_STATUS)
  const [agentMessages, setAgentMessages] = useState<AgentMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)

  const esRef = useRef<EventSource | null>(null)
  const stoppedRef = useRef(false)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const callbacksRef = useRef(callbacks)
  useEffect(() => {
    callbacksRef.current = callbacks
  })

  useEffect(() => {
    if (!runId) {
      setRunStatus(DEFAULT_RUN_STATUS)
      setAgentMessages([])
      setIsConnected(false)
      return
    }

    stoppedRef.current = false
    reconnectDelayRef.current = INITIAL_RECONNECT_DELAY

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }

    const handleTerminal = async (status: RunStatusType) => {
      stoppedRef.current = true
      esRef.current?.close()
      esRef.current = null
      setIsConnected(false)

      // SSE status 이벤트에는 response가 없으므로 폴링 API로 최종 상태 가져오기
      try {
        const finalStatus = await api.getRunStatus(runId)
        setRunStatus(finalStatus)
        if (status === 'done' && finalStatus.response != null) {
          callbacksRef.current?.onDone?.(
            finalStatus.response,
            finalStatus.mode,
            finalStatus.model,
            finalStatus.timing ?? null,
          )
        } else if (status === 'error') {
          callbacksRef.current?.onError?.(finalStatus.response)
        } else if (status === 'cancelled') {
          callbacksRef.current?.onCancelled?.()
        }
      } catch {
        // API 오류 시 콜백만 호출
        if (status === 'done') callbacksRef.current?.onDone?.('', null, null, null)
        else if (status === 'error') callbacksRef.current?.onError?.(null)
        else if (status === 'cancelled') callbacksRef.current?.onCancelled?.()
      }
    }

    const handleMessage = (data: SSEEvent) => {
      switch (data.type) {
        case 'status': {
          const newStatus = data.status as RunStatusType | undefined
          if (!newStatus) break
          setRunStatus((prev) => ({
            ...prev,
            status: newStatus,
            progress: data.progress ?? prev.progress,
            mode: data.mode ?? prev.mode,
          }))
          if (TERMINAL_STATES.includes(newStatus)) {
            void handleTerminal(newStatus)
          }
          break
        }

        case 'agent_message_created': {
          const msg = data.agent_message
          if (msg) {
            setAgentMessages((prev) =>
              prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
            )
          }
          break
        }

        case 'content': {
          const agent = data.agent
          const content = data.content
          if (agent !== undefined && content !== undefined) {
            setAgentMessages((prev) =>
              prev.map((m) => (m.sender === agent ? { ...m, content } : m)),
            )
          }
          break
        }

        case 'agent_status_changed': {
          const msgId = data.agent_message_id
          const agentStatus = data.status
          if (msgId && agentStatus) {
            setAgentMessages((prev) =>
              prev.map((m) =>
                m.id === msgId
                  ? { ...m, status: agentStatus as AgentMessage['status'] }
                  : m,
              ),
            )
          }
          break
        }

        default:
          break
      }
    }

    const connect = () => {
      if (stoppedRef.current) return

      const es = new EventSource(`/api/runs/${runId}/stream`)
      esRef.current = es

      es.onopen = () => {
        setIsConnected(true)
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY
      }

      es.onmessage = (event: MessageEvent<string>) => {
        try {
          const data: SSEEvent = JSON.parse(event.data) as SSEEvent
          handleMessage(data)
        } catch {
          /* JSON 파싱 오류 무시 */
        }
      }

      es.onerror = () => {
        setIsConnected(false)
        es.close()
        esRef.current = null

        if (!stoppedRef.current) {
          // 지수 백오프 재연결
          reconnectTimerRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(
              reconnectDelayRef.current * 2,
              MAX_RECONNECT_DELAY,
            )
            connect()
          }, reconnectDelayRef.current)
        }
      }
    }

    connect()

    return () => {
      stoppedRef.current = true
      clearReconnectTimer()
      esRef.current?.close()
      esRef.current = null
      setIsConnected(false)
    }
  }, [runId])

  return {
    runStatus: runId ? runStatus : DEFAULT_RUN_STATUS,
    agentMessages,
    isConnected,
  }
}
