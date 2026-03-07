import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import type { Session, SessionDetail, UserMessage } from '../types/api'

export interface UseSessionResult {
  sessions: Session[]
  currentSession: Session | null
  messages: UserMessage[]
  switchSession: (id: string) => Promise<SessionDetail>
  createSession: () => Promise<void>
  deleteSession: (id: string) => Promise<void>
  addMessage: (msg: UserMessage) => void
  setCurrentSessionFromChat: (sessionId: string) => void
  refreshSessions: () => Promise<void>
}

export function useSession(): UseSessionResult {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<UserMessage[]>([])
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Bug 3: currentSession?.id를 ref로 관리해 비동기 처리 중 클로저 캡처 문제 방지
  const currentSessionIdRef = useRef<string | undefined>(currentSession?.id)
  useEffect(() => {
    currentSessionIdRef.current = currentSession?.id
  })

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  const switchSession = useCallback(async (id: string) => {
    const detail = await api.getSession(id)
    setCurrentSession(detail)
    setMessages(detail.messages)
    return detail
  }, [])

  const createSession = useCallback(async () => {
    const sess = await api.createSession()
    setSessions((prev) => [sess, ...prev])
    setCurrentSession(sess)
    setMessages([])
  }, [])

  const deleteSession = useCallback(async (id: string) => {
    try {
      await api.deleteSession(id)
    } catch {
      // 이미 없는 세션이면 목록만 갱신
    }
    const list = await api.getSessions()
    setSessions(list)
    // Bug 3: 클로저 캡처 대신 ref로 최신 currentSession?.id 참조
    if (currentSessionIdRef.current === id) {
      if (list.length > 0) {
        const detail = await api.getSession(list[0].id)
        setCurrentSession(detail)
        setMessages(detail.messages)
      } else {
        const sess = await api.createSession()
        setSessions([sess])
        setCurrentSession(sess)
        setMessages([])
      }
    } else {
      setCurrentSession((prev) => (prev ? list.find((s) => s.id === prev.id) ?? prev : null))
    }
  }, [])

  const addMessage = useCallback((msg: UserMessage) => {
    setMessages((prev) => [...prev, msg])
    if (msg.role === 'reader') {
      // 짧은 시간 내 연속 호출 시 목록 깜빡임 방지: 300ms 디바운스
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = setTimeout(() => {
        api.getSessions().then((list) => {
          setSessions(list)
          setCurrentSession((prev) => {
            if (!prev) return prev
            return list.find((s) => s.id === prev.id) ?? prev
          })
        }).catch(() => {})
      }, 300)
    }
  }, [])

  const setCurrentSessionFromChat = useCallback((sessionId: string) => {
    const pseudo: Session = {
      id: sessionId,
      title: null,
      llm_provider: 'claude-cli',
      llm_model: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setCurrentSession(pseudo)
    setSessions((prev) => {
      if (prev.find((s) => s.id === sessionId)) return prev
      return [pseudo, ...prev]
    })
  }, [])

  const refreshSessions = useCallback(async () => {
    const list = await api.getSessions()
    setSessions(list)
    setCurrentSession((prev) => {
      if (!prev) return prev
      return list.find((s) => s.id === prev.id) ?? prev
    })
  }, [])

  return {
    sessions,
    currentSession,
    messages,
    switchSession,
    createSession,
    deleteSession,
    addMessage,
    setCurrentSessionFromChat,
    refreshSessions,
  }
}
