import { useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import type { RunStatus, RunStatusType, TimingInfo } from '../types/api'

const TERMINAL_STATES: RunStatusType[] = ['done', 'error', 'cancelled']

const DEFAULT_STATE: RunStatus = {
  status: 'queued',
  progress: null,
  response: null,
  mode: null,
  model: null,
  agents: null,
  timing: null,
}

export interface RunPollingCallbacks {
  onDone?: (
    response: string,
    mode: 'solo' | 'team' | null,
    model: string | null,
    timing: TimingInfo | null,
  ) => void
  onError?: (errorResponse: string | null) => void
  onCancelled?: () => void
}

export function useRunPolling(
  runId: string | null,
  callbacks?: RunPollingCallbacks,
): RunStatus {
  const [state, setState] = useState<RunStatus>(DEFAULT_STATE)
  const stoppedRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const callbacksRef = useRef(callbacks)
  useEffect(() => {
    callbacksRef.current = callbacks
  })

  useEffect(() => {
    if (!runId) return

    stoppedRef.current = false

    const poll = async () => {
      try {
        const data = await api.getRunStatus(runId)
        setState(data)

        if (TERMINAL_STATES.includes(data.status)) {
          stoppedRef.current = true
          if (data.status === 'done' && data.response != null) {
            callbacksRef.current?.onDone?.(data.response, data.mode, data.model, data.timing ?? null)
          } else if (data.status === 'error') {
            callbacksRef.current?.onError?.(data.response)
          } else if (data.status === 'cancelled') {
            callbacksRef.current?.onCancelled?.()
          }
          return
        }
      } catch {
        // 일시적 오류 무시
      }

      if (!stoppedRef.current) {
        const interval = 2000 + Math.random() * 600 - 300
        timerRef.current = setTimeout(poll, interval)
      }
    }

    poll()

    return () => {
      stoppedRef.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [runId])

  return runId ? state : DEFAULT_STATE
}
